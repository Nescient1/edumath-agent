import hashlib
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from pipeline_utils import RAW_DIR, RAW_TEMP_DIR, ensure_pipeline_dirs, relative_to_backend, write_json


SOLUTION_MARKERS = ["解析版", "含解析", "答案解析", "详解", "解析", "答案"]
ORIGINAL_ONLY_MARKERS = ["原卷版", "试题版", "无答案", "学生版"]
SUPPORTED_IMPORT_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".html", ".htm"}
EXTENSION_PRIORITY = {".docx": 5, ".pdf": 4, ".md": 3, ".txt": 2, ".html": 1, ".htm": 1}
TARGET_DIR = RAW_DIR / "exams_with_solution" / "raw_temp_imported"


@dataclass
class Candidate:
    path: Path
    relative_path: str
    title_key: str
    file_hash: str
    extension: str
    size: int
    has_solution: bool
    is_original_only: bool
    priority: int


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_title_key(path: Path) -> str:
    name = path.stem
    for marker in SOLUTION_MARKERS + ORIGINAL_ONLY_MARKERS:
        name = name.replace(f"({marker})", "")
        name = name.replace(f"（{marker}）", "")
        name = name.replace(marker, "")
    name = re.sub(r"[-_—\s]+", "", name)
    name = re.sub(r"\d{4}年新高考数学之", "", name)
    return name


def safe_filename(candidate: Candidate, index: int) -> str:
    topic = re.sub(r'[<>:"/\\|?*\s]+', "_", candidate.path.stem)
    topic = topic.strip("._")[:120] or f"material_{index:04d}"
    return f"{index:04d}_{topic}{candidate.extension}"


def score_candidate(path: Path, relative_path: str) -> Candidate:
    extension = path.suffix.lower()
    text = f"{relative_path} {path.name}"
    has_solution = any(marker in text for marker in SOLUTION_MARKERS)
    is_original_only = any(marker in text for marker in ORIGINAL_ONLY_MARKERS)
    extension_score = EXTENSION_PRIORITY.get(extension, 0)
    priority = extension_score + (100 if has_solution else 0) - (80 if is_original_only else 0)
    return Candidate(
        path=path,
        relative_path=relative_path,
        title_key=normalize_title_key(path),
        file_hash=file_sha256(path),
        extension=extension,
        size=path.stat().st_size,
        has_solution=has_solution,
        is_original_only=is_original_only,
        priority=priority,
    )


def collect_candidates() -> list[Candidate]:
    raw_root = RAW_TEMP_DIR.resolve()
    candidates: list[Candidate] = []
    for path in RAW_TEMP_DIR.rglob("*"):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        relative_path = str(path.resolve().relative_to(raw_root))
        candidates.append(score_candidate(path, relative_path))
    return candidates


def choose_best_candidates(candidates: list[Candidate]) -> tuple[list[Candidate], list[dict]]:
    by_hash: dict[str, Candidate] = {}
    skipped: list[dict] = []

    for candidate in candidates:
        if candidate.extension not in SUPPORTED_IMPORT_EXTENSIONS:
            skipped.append(
                {
                    "source_path": candidate.relative_path,
                    "reason": f"unsupported_extension:{candidate.extension}",
                }
            )
            continue
        if not candidate.has_solution:
            skipped.append(
                {
                    "source_path": candidate.relative_path,
                    "reason": "not_solution_version",
                }
            )
            continue
        existing = by_hash.get(candidate.file_hash)
        if existing is None or candidate.priority > existing.priority:
            if existing is not None:
                skipped.append(
                    {
                        "source_path": existing.relative_path,
                        "reason": "duplicate_hash_lower_priority",
                        "kept": candidate.relative_path,
                    }
                )
            by_hash[candidate.file_hash] = candidate
        else:
            skipped.append(
                {
                    "source_path": candidate.relative_path,
                    "reason": "duplicate_hash",
                    "kept": existing.relative_path,
                }
            )

    grouped: dict[str, Candidate] = {}
    for candidate in by_hash.values():
        existing = grouped.get(candidate.title_key)
        if existing is None:
            grouped[candidate.title_key] = candidate
            continue
        if (candidate.priority, candidate.size) > (existing.priority, existing.size):
            skipped.append(
                {
                    "source_path": existing.relative_path,
                    "reason": "duplicate_topic_lower_priority",
                    "kept": candidate.relative_path,
                }
            )
            grouped[candidate.title_key] = candidate
        else:
            skipped.append(
                {
                    "source_path": candidate.relative_path,
                    "reason": "duplicate_topic",
                    "kept": existing.relative_path,
                }
            )

    return sorted(grouped.values(), key=lambda item: item.relative_path), skipped


def import_candidates(candidates: list[Candidate]) -> list[dict]:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    imported = []
    for index, candidate in enumerate(candidates, start=1):
        target_path = TARGET_DIR / safe_filename(candidate, index)
        shutil.copy2(candidate.path, target_path)
        record = asdict(candidate)
        record["path"] = str(candidate.path)
        record["target_path"] = relative_to_backend(target_path)
        imported.append(record)
    return imported


def main() -> None:
    ensure_pipeline_dirs()
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    candidates = collect_candidates()
    selected, skipped = choose_best_candidates(candidates)
    imported = import_candidates(selected)
    manifest = {
        "source_dir": relative_to_backend(RAW_TEMP_DIR),
        "target_dir": relative_to_backend(TARGET_DIR),
        "candidate_count": len(candidates),
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "imported": imported,
        "skipped": skipped,
    }
    write_json(RAW_DIR / "raw_temp_import_manifest.json", manifest)
    print(f"Input: {RAW_TEMP_DIR}")
    print(f"Output: {TARGET_DIR}")
    print(
        f"Raw temp prepared: candidates={len(candidates)}, "
        f"imported={len(imported)}, skipped={len(skipped)}"
    )


if __name__ == "__main__":
    main()
