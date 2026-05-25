import argparse
import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
RAW_TEMP_DIR = DATA_DIR / "raw_temp"
RAW_LECTURES_DIR = DATA_DIR / "raw" / "lectures"
TOPIC_MAP = {
    "函数": "function",
    "导数": "derivative",
}
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}
EXTENSION_PRIORITY = {".pdf": 40, ".docx": 30, ".md": 20, ".txt": 10}
SOLUTION_MARKERS = ("教师版", "解析版", "含解析", "答案", "详解")
LOW_PRIORITY_MARKERS = ("学生版", "原卷版", "试题版", "无答案")


@dataclass
class ImportCandidate:
    source_path: str
    target_topic: str
    normalized_key: str
    file_hash: str
    extension: str
    size: int
    score: int
    selected: bool = False
    target_path: str | None = None
    skip_reason: str | None = None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_key(path: Path) -> str:
    text = path.stem
    text = re.sub(r"\.docx$", "", text, flags=re.IGNORECASE)
    for marker in SOLUTION_MARKERS + LOW_PRIORITY_MARKERS:
        text = text.replace(marker, "")
        text = text.replace(f"({marker})", "")
        text = text.replace(f"（{marker}）", "")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[()（）【】\[\]_\-—]+", "", text)
    return text[:160]


def score_file(path: Path) -> int:
    name = str(path)
    score = EXTENSION_PRIORITY.get(path.suffix.lower(), 0)
    if any(marker in name for marker in SOLUTION_MARKERS):
        score += 100
    if any(marker in name for marker in LOW_PRIORITY_MARKERS):
        score -= 80
    if "教师版" in name:
        score += 20
    if "解析版" in name:
        score += 15
    return score


def safe_filename(index: int, source: Path) -> str:
    stem = re.sub(r'[<>:"/\\|?*\s]+', "_", source.stem).strip("._")
    stem = stem[:120] or f"material_{index:04d}"
    return f"{index:04d}_{stem}{source.suffix.lower()}"


def collect_candidates() -> list[tuple[Path, ImportCandidate]]:
    pairs: list[tuple[Path, ImportCandidate]] = []
    for chinese_topic, target_topic in TOPIC_MAP.items():
        source_dir = RAW_TEMP_DIR / chinese_topic
        if not source_dir.exists():
            continue
        for path in source_dir.rglob("*"):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            extension = path.suffix.lower()
            if extension == ".doc" and path.name.lower().endswith(".docx.doc"):
                extension = ".doc"
            relative = str(path.relative_to(BACKEND_DIR))
            candidate = ImportCandidate(
                source_path=relative,
                target_topic=target_topic,
                normalized_key=normalize_key(path),
                file_hash=file_sha256(path),
                extension=extension,
                size=path.stat().st_size,
                score=score_file(path),
            )
            pairs.append((path, candidate))
    return pairs


def choose_candidates(pairs: list[tuple[Path, ImportCandidate]]) -> tuple[list[tuple[Path, ImportCandidate]], list[ImportCandidate]]:
    skipped: list[ImportCandidate] = []
    by_hash: dict[str, tuple[Path, ImportCandidate]] = {}

    for path, candidate in pairs:
        if candidate.extension not in SUPPORTED_EXTENSIONS:
            candidate.skip_reason = f"unsupported_extension:{candidate.extension}"
            skipped.append(candidate)
            continue
        if any(marker in candidate.source_path for marker in LOW_PRIORITY_MARKERS) and not any(
            marker in candidate.source_path for marker in SOLUTION_MARKERS
        ):
            candidate.skip_reason = "student_or_original_without_solution"
            skipped.append(candidate)
            continue
        existing = by_hash.get(candidate.file_hash)
        if existing is None or candidate.score > existing[1].score:
            if existing is not None:
                existing[1].skip_reason = "duplicate_hash_lower_score"
                skipped.append(existing[1])
            by_hash[candidate.file_hash] = (path, candidate)
        else:
            candidate.skip_reason = "duplicate_hash"
            skipped.append(candidate)

    grouped: dict[tuple[str, str], tuple[Path, ImportCandidate]] = {}
    for path, candidate in by_hash.values():
        key = (candidate.target_topic, candidate.normalized_key)
        existing = grouped.get(key)
        if existing is None or (candidate.score, candidate.size) > (existing[1].score, existing[1].size):
            if existing is not None:
                existing[1].skip_reason = "duplicate_topic_lower_score"
                skipped.append(existing[1])
            grouped[key] = (path, candidate)
        else:
            candidate.skip_reason = "duplicate_topic"
            skipped.append(candidate)

    selected = sorted(grouped.values(), key=lambda item: (item[1].target_topic, item[1].source_path))
    for _, candidate in selected:
        candidate.selected = True
    return selected, skipped


def import_selected(selected: list[tuple[Path, ImportCandidate]]) -> list[ImportCandidate]:
    counters = {topic: 0 for topic in TOPIC_MAP.values()}
    imported: list[ImportCandidate] = []
    for source_path, candidate in selected:
        counters[candidate.target_topic] += 1
        target_dir = RAW_LECTURES_DIR / candidate.target_topic
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / safe_filename(counters[candidate.target_topic], source_path)
        shutil.copy2(source_path, target_path)
        candidate.target_path = str(target_path.relative_to(BACKEND_DIR))
        imported.append(candidate)
    return imported


def main() -> int:
    parser = argparse.ArgumentParser(description="Import curated function/derivative materials from raw_temp.")
    parser.add_argument("--dry-run", action="store_true", help="Only write manifest; do not copy files.")
    args = parser.parse_args()

    pairs = collect_candidates()
    selected, skipped = choose_candidates(pairs)
    imported = selected if args.dry_run else [(None, item) for item in import_selected(selected)]

    manifest = {
        "source_dir": str(RAW_TEMP_DIR.relative_to(BACKEND_DIR)),
        "target_dir": str(RAW_LECTURES_DIR.relative_to(BACKEND_DIR)),
        "candidate_count": len(pairs),
        "selected_count": len(selected),
        "skipped_count": len(skipped),
        "dry_run": args.dry_run,
        "imported": [asdict(item[1] if isinstance(item, tuple) else item) for item in imported],
        "skipped": [asdict(item) for item in skipped],
    }
    output_path = DATA_DIR / "raw" / "raw_temp_function_derivative_manifest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"candidates={len(pairs)} selected={len(selected)} skipped={len(skipped)}")
    print(f"manifest={output_path}")
    if not args.dry_run:
        print(f"target={RAW_LECTURES_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
