from __future__ import annotations

import argparse
import shutil
import sys
from collections import defaultdict
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline_utils import RAW_DIR, relative_to_backend, write_json


DEFAULT_SOURCE_DIR = RAW_DIR / "temp"
DEFAULT_TARGET_DIR = RAW_DIR / "lectures"
DEFAULT_MANIFEST_NAME = "teacher_lectures_manifest.json"

PREFERRED_EXTENSIONS = (".docx", ".pdf")
EXTENSION_PRIORITY = {".docx": 0, ".pdf": 1}


def is_teacher_file(path: Path) -> bool:
    name = path.name
    return (
        path.is_file()
        and "学生版" not in name
        and "教师版" in name
        and path.suffix.lower() in PREFERRED_EXTENSIONS
    )


def teacher_group_key(source_dir: Path, path: Path) -> tuple[str, ...]:
    relative = path.relative_to(source_dir)
    return (*relative.parent.parts, path.stem)


def choose_best_file(files: list[Path]) -> Path:
    return sorted(
        files,
        key=lambda path: (EXTENSION_PRIORITY.get(path.suffix.lower(), 99), path.name),
    )[0]


def collect_teacher_files(source_dir: Path) -> tuple[list[Path], list[dict[str, str]]]:
    groups: dict[tuple[str, ...], list[Path]] = defaultdict(list)
    skipped: list[dict[str, str]] = []

    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue

        name = path.name
        suffix = path.suffix.lower()

        if "学生版" in name:
            skipped.append(
                {
                    "path": str(path.relative_to(source_dir)),
                    "reason": "学生版资料，跳过",
                }
            )
            continue

        if "教师版" not in name:
            skipped.append(
                {
                    "path": str(path.relative_to(source_dir)),
                    "reason": "不是教师版资料，跳过",
                }
            )
            continue

        if suffix not in PREFERRED_EXTENSIONS:
            skipped.append(
                {
                    "path": str(path.relative_to(source_dir)),
                    "reason": f"暂不支持 {suffix or '无后缀'}，跳过",
                }
            )
            continue

        groups[teacher_group_key(source_dir, path)].append(path)

    selected: list[Path] = []
    for files in groups.values():
        chosen = choose_best_file(files)
        selected.append(chosen)

        for file in files:
            if file == chosen:
                continue
            skipped.append(
                {
                    "path": str(file.relative_to(source_dir)),
                    "reason": f"同一教师版资料已选择 {chosen.suffix.lower()}，跳过备选文件",
                }
            )

    return sorted(selected), skipped


def copy_selected_files(
    selected: list[Path],
    source_dir: Path,
    target_dir: Path,
    dry_run: bool,
) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []

    for source_path in selected:
        relative = source_path.relative_to(source_dir)
        target_path = target_dir / relative

        if not dry_run:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

        copied.append(
            {
                "source": str(relative),
                "target": str(target_path.relative_to(target_dir)),
                "format": source_path.suffix.lower(),
            }
        )

    return copied


def build_manifest(
    copied: list[dict[str, str]],
    skipped: list[dict[str, str]],
    source_dir: Path,
    target_dir: Path,
    dry_run: bool,
) -> dict[str, object]:
    return {
        "source_dir": relative_to_backend(source_dir),
        "target_dir": relative_to_backend(target_dir),
        "selection_rule": "优先选择教师版 .docx；没有 .docx 时选择教师版 .pdf；跳过学生版和 .doc。",
        "dry_run": dry_run,
        "summary": {
            "selected": len(copied),
            "skipped": len(skipped),
            "docx": sum(1 for item in copied if item["format"] == ".docx"),
            "pdf": sum(1 for item in copied if item["format"] == ".pdf"),
        },
        "selected_files": copied,
        "skipped_files": sorted(skipped, key=lambda item: item["path"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从 raw/temp 中筛选教师版讲义，整理到 raw/lectures。"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="原始临时资料目录，默认 backend/data/raw/temp",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET_DIR,
        help="整理后的讲义目录，默认 backend/data/raw/lectures",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只生成清单，不复制文件",
    )
    args = parser.parse_args()

    source_dir = args.source.resolve()
    target_dir = args.target.resolve()

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    selected, skipped = collect_teacher_files(source_dir)
    copied = copy_selected_files(selected, source_dir, target_dir, args.dry_run)
    manifest = build_manifest(copied, skipped, source_dir, target_dir, args.dry_run)

    if not args.dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
    write_json(target_dir / DEFAULT_MANIFEST_NAME, manifest)

    summary = manifest["summary"]
    print(
        "Prepared teacher lectures: "
        f"{summary['selected']} selected "
        f"({summary['docx']} docx, {summary['pdf']} pdf), "
        f"{summary['skipped']} skipped."
    )
    print(f"Manifest: {relative_to_backend(target_dir / DEFAULT_MANIFEST_NAME)}")


if __name__ == "__main__":
    main()
