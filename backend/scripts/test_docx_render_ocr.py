import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.pix2text_service import (
    is_pix2text_installed,
    recognize_image_with_pix2text,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BACKEND_DIR / "data" / "raw"
OUTPUT_ROOT = BACKEND_DIR / "data" / "ocr_trials" / "docx_render_samples"


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


def _convert_with_libreoffice(docx_path: Path, output_dir: Path) -> tuple[Path | None, str | None]:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None, "LibreOffice/soffice not found"

    command = [
        soffice,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(docx_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
    pdf_path = output_dir / f"{docx_path.stem}.pdf"
    if completed.returncode == 0 and pdf_path.exists():
        return pdf_path, None
    return None, (completed.stderr or completed.stdout or "LibreOffice conversion failed").strip()


def _convert_with_word_com(docx_path: Path, output_dir: Path) -> tuple[Path | None, str | None]:
    if platform.system().lower() != "windows":
        return None, "Microsoft Word COM is only available on Windows"

    pdf_path = output_dir / f"{docx_path.stem}.pdf"
    script = f"""
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {{
  $doc = $word.Documents.Open('{str(docx_path)}')
  $doc.SaveAs([ref]'{str(pdf_path)}', [ref]17)
  $doc.Close([ref]$false)
}} finally {{
  $word.Quit()
}}
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.returncode == 0 and pdf_path.exists():
        return pdf_path, None
    return None, (completed.stderr or completed.stdout or "Word COM conversion failed").strip()


def convert_docx_to_pdf(docx_path: Path, output_dir: Path) -> tuple[Path | None, list[str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    for converter in (_convert_with_libreoffice, _convert_with_word_com):
        pdf_path, error = converter(docx_path.resolve(), output_dir.resolve())
        if pdf_path:
            return pdf_path, errors
        if error:
            errors.append(error)

    return None, errors


def render_pdf_pages(pdf_path: Path, output_dir: Path, *, dpi: int, max_pages: int) -> list[dict]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Missing dependency: PyMuPDF. Install with `pip install pymupdf`.") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    document = fitz.open(str(pdf_path))
    rendered: list[dict] = []
    page_count = min(len(document), max_pages)

    for page_index in range(page_count):
        page = document[page_index]
        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
        image_path = output_dir / f"page_{page_index + 1:03d}_{dpi}dpi.png"
        pixmap.save(str(image_path))
        rendered.append(
            {
                "page": page_index + 1,
                "image_path": str(image_path),
                "width": pixmap.width,
                "height": pixmap.height,
                "dpi": dpi,
            }
        )

    document.close()
    return rendered


def run_trial(
    docx_path: Path,
    output_root: Path,
    *,
    dpi: int,
    max_pages: int,
    run_ocr: bool,
    pdf_input: Path | None = None,
) -> dict:
    trial_dir = output_root / _safe_stem(docx_path)
    pdf_dir = trial_dir / "pdf"
    pages_dir = trial_dir / "pages"

    conversion_errors: list[str] = []
    if pdf_input:
        pdf_path = pdf_input.resolve()
        if not pdf_path.exists():
            conversion_errors.append(f"PDF input not found: {pdf_path}")
            pdf_path = None
    else:
        pdf_path, conversion_errors = convert_docx_to_pdf(docx_path, pdf_dir)
    page_records: list[dict] = []
    if pdf_path:
        page_records = render_pdf_pages(pdf_path, pages_dir, dpi=dpi, max_pages=max_pages)

    pix2text_installed = is_pix2text_installed()
    if run_ocr and pix2text_installed:
        for record in page_records:
            result = recognize_image_with_pix2text(Path(record["image_path"]))
            record["ocr_status"] = "failed" if result.error else "success"
            record["ocr_error"] = result.error
            record["ocr_text"] = result.text
    elif run_ocr:
        for record in page_records:
            record["ocr_status"] = "skipped"
            record["ocr_error"] = "pix2text is not installed"
            record["ocr_text"] = ""

    report = {
        "docx_path": str(docx_path),
        "pdf_input": str(pdf_input) if pdf_input else None,
        "output_dir": str(trial_dir),
        "pdf_path": str(pdf_path) if pdf_path else None,
        "conversion_status": "success" if pdf_path else "failed",
        "conversion_errors": conversion_errors,
        "dpi": dpi,
        "max_pages": max_pages,
        "rendered_pages": len(page_records),
        "run_ocr": run_ocr,
        "pix2text_installed": pix2text_installed,
        "pages": page_records,
    }
    report_path = trial_dir / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Render DOCX to high-DPI page images and optionally OCR.")
    parser.add_argument("--docx", default=None, help="DOCX path or glob under backend/data/raw.")
    parser.add_argument("--pdf", default=None, help="Optional pre-exported PDF path.")
    parser.add_argument("--dpi", type=int, default=220, help="PDF page render DPI.")
    parser.add_argument("--pages", type=int, default=2, help="Max pages to render.")
    parser.add_argument("--run-ocr", action="store_true", help="Run full Pix2Text OCR on rendered page images.")
    parser.add_argument("--output-dir", default=str(OUTPUT_ROOT), help="Trial output directory.")
    args = parser.parse_args()

    docx_path = _find_docx(args.docx)
    pdf_input = Path(args.pdf) if args.pdf else None
    report = run_trial(
        docx_path,
        Path(args.output_dir),
        dpi=args.dpi,
        max_pages=args.pages,
        run_ocr=args.run_ocr,
        pdf_input=pdf_input,
    )

    print(f"DOCX: {report['docx_path']}")
    print(f"Output: {report['output_dir']}")
    print(f"Conversion: {report['conversion_status']}")
    if report["pdf_path"]:
        print(f"PDF: {report['pdf_path']}")
    if report["conversion_errors"]:
        print("Conversion errors:")
        for error in report["conversion_errors"]:
            print(f"- {error[:500]}")
    print(f"Rendered pages: {report['rendered_pages']}")
    for page in report["pages"][:3]:
        print(f"- page {page['page']}: {page['image_path']} ({page['width']}x{page['height']})")
        if args.run_ocr:
            print(f"  ocr={page.get('ocr_status')} {page.get('ocr_error') or ''}")
            text = page.get("ocr_text") or ""
            if text:
                print(text[:500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
