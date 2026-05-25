import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.pix2text_service import (
    is_pix2text_installed,
    recognize_formula_image_with_pix2text,
    recognize_image_with_pix2text,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BACKEND_DIR / "data" / "raw"
OUTPUT_ROOT = BACKEND_DIR / "data" / "ocr_trials" / "pix2text_samples"
RASTER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
VECTOR_EXTENSIONS = {".wmf", ".emf"}
MIN_OCR_WIDTH = 640
MIN_OCR_HEIGHT = 96
OCR_PADDING = 24


def _safe_stem(path: Path) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    return f"{path.stem}_{digest}"


def _find_docx(pattern: str | None) -> Path:
    if pattern:
        path = Path(pattern)
        if path.exists():
            return path
        matches = list(RAW_DIR.rglob(pattern))
        if matches:
            return matches[0]
        raise FileNotFoundError(f"No docx matched: {pattern}")

    matches = list(RAW_DIR.rglob("*.docx"))
    if not matches:
        raise FileNotFoundError(f"No docx files found under {RAW_DIR}.")
    return matches[0]


def _convert_with_command(input_path: Path, output_path: Path) -> str | None:
    commands = []
    magick = shutil.which("magick")
    if magick:
        commands.append([magick, str(input_path), str(output_path)])
    inkscape = shutil.which("inkscape")
    if inkscape:
        commands.append(
            [
                inkscape,
                str(input_path),
                "--export-type=png",
                f"--export-filename={output_path}",
            ]
        )

    for command in commands:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=30,
            )
        except Exception as exc:
            last_error = str(exc)
            continue
        if completed.returncode == 0 and output_path.exists():
            return None
        last_error = (completed.stderr or completed.stdout or "").strip()
    return last_error if commands else "No converter found: install ImageMagick or Inkscape."


def _convert_vector_to_png(input_path: Path, output_path: Path) -> str | None:
    command_error = _convert_with_command(input_path, output_path)
    if command_error is None and output_path.exists():
        return None

    try:
        from PIL import Image

        with Image.open(input_path) as image:
            image.save(output_path)
        if output_path.exists():
            return None
    except Exception as exc:
        pil_error = str(exc)
    return command_error or pil_error


def _prepare_ocr_image(input_path: Path, output_path: Path) -> str | None:
    try:
        from PIL import Image, ImageOps

        with Image.open(input_path) as image:
            image = image.convert("RGBA")
            background = Image.new("RGBA", image.size, "WHITE")
            background.alpha_composite(image)
            image = background.convert("RGB")

            scale = max(
                1,
                int(max(MIN_OCR_WIDTH / max(image.width, 1), MIN_OCR_HEIGHT / max(image.height, 1))),
            )
            if scale > 1:
                image = image.resize(
                    (image.width * scale, image.height * scale),
                    Image.Resampling.LANCZOS,
                )
            image = ImageOps.expand(image, border=OCR_PADDING, fill="WHITE")
            image.save(output_path)
        return None
    except Exception as exc:
        return str(exc)


def extract_docx_media(docx_path: Path, output_dir: Path, limit: int) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []

    with zipfile.ZipFile(docx_path) as archive:
        media_names = [
            name
            for name in archive.namelist()
            if name.startswith("word/media/") and not name.endswith("/")
        ]
        for index, name in enumerate(media_names[:limit], start=1):
            ext = Path(name).suffix.lower()
            raw_name = f"{index:03d}_{Path(name).name}"
            raw_path = output_dir / raw_name
            raw_path.write_bytes(archive.read(name))

            record = {
                "index": index,
                "media_name": name,
                "extension": ext or "unknown",
                "raw_path": str(raw_path),
                "ocr_image_path": None,
                "conversion_status": "skipped",
                "conversion_error": None,
            }
            candidate_image: Path | None = None
            if ext in RASTER_EXTENSIONS:
                candidate_image = raw_path
                record["conversion_status"] = "native_raster"
            elif ext in VECTOR_EXTENSIONS:
                png_path = output_dir / f"{raw_path.stem}.png"
                error = _convert_vector_to_png(raw_path, png_path)
                if error:
                    record["conversion_status"] = "failed"
                    record["conversion_error"] = error
                else:
                    candidate_image = png_path
                    record["conversion_status"] = "converted_to_png"
            else:
                record["conversion_status"] = "unsupported_extension"

            if candidate_image is not None:
                prepared_path = output_dir / f"{candidate_image.stem}_ocr.png"
                prepare_error = _prepare_ocr_image(candidate_image, prepared_path)
                if prepare_error:
                    record["ocr_image_path"] = str(candidate_image)
                    record["prepare_status"] = "failed"
                    record["prepare_error"] = prepare_error
                else:
                    record["ocr_image_path"] = str(prepared_path)
                    record["prepare_status"] = "success"
                    record["prepare_error"] = None
            records.append(record)

    return records


def run_trial(docx_path: Path, limit: int, output_root: Path, mode: str) -> dict:
    trial_dir = output_root / _safe_stem(docx_path)
    media_dir = trial_dir / "media"
    media_records = extract_docx_media(docx_path, media_dir, limit)

    installed = is_pix2text_installed()
    for record in media_records:
        image_path = record.get("ocr_image_path")
        if not installed:
            record["ocr_status"] = "skipped"
            record["ocr_error"] = "pix2text is not installed"
            record["ocr_text"] = ""
            continue
        if not image_path:
            record["ocr_status"] = "skipped"
            record["ocr_error"] = record.get("conversion_error") or "no OCR image"
            record["ocr_text"] = ""
            continue

        if mode == "formula":
            result = recognize_formula_image_with_pix2text(Path(image_path))
        else:
            result = recognize_image_with_pix2text(Path(image_path))
        record["ocr_status"] = "failed" if result.error else "success"
        record["ocr_error"] = result.error
        record["ocr_text"] = result.text

    report = {
        "docx_path": str(docx_path),
        "limit": limit,
        "mode": mode,
        "pix2text_installed": installed,
        "output_dir": str(trial_dir),
        "media_count_sampled": len(media_records),
        "converted_count": sum(
            1 for item in media_records if item["conversion_status"] == "converted_to_png"
        ),
        "native_raster_count": sum(
            1 for item in media_records if item["conversion_status"] == "native_raster"
        ),
        "conversion_failed_count": sum(
            1 for item in media_records if item["conversion_status"] == "failed"
        ),
        "ocr_success_count": sum(
            1 for item in media_records if item.get("ocr_status") == "success"
        ),
        "items": media_records,
    }
    report_path = trial_dir / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Pix2Text trial on DOCX media.")
    parser.add_argument("--docx", default=None, help="DOCX path or glob under backend/data/raw.")
    parser.add_argument("--limit", type=int, default=20, help="Max media files to sample.")
    parser.add_argument(
        "--mode",
        default="formula",
        choices=("formula", "page"),
        help="formula uses Pix2Text LatexOCR; page uses full Pix2Text document OCR.",
    )
    parser.add_argument("--output-dir", default=str(OUTPUT_ROOT), help="Trial output directory.")
    args = parser.parse_args()

    docx_path = _find_docx(args.docx)
    report = run_trial(docx_path, args.limit, Path(args.output_dir), args.mode)
    print(f"DOCX: {report['docx_path']}")
    print(f"Output: {report['output_dir']}")
    print(f"Mode: {report['mode']}")
    print(f"Pix2Text installed: {report['pix2text_installed']}")
    print(
        "Sampled={media_count_sampled}, native_raster={native_raster_count}, "
        "converted={converted_count}, conversion_failed={conversion_failed_count}, "
        "ocr_success={ocr_success_count}".format(**report)
    )

    for item in report["items"][:5]:
        print("\n--- sample", item["index"], item["extension"], "---")
        print("conversion:", item["conversion_status"], item.get("conversion_error") or "")
        print("ocr:", item.get("ocr_status"), item.get("ocr_error") or "")
        text = item.get("ocr_text") or ""
        if text:
            print(text[:500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
