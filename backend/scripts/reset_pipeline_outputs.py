import argparse
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
DEFAULT_TARGETS = [
    DATA_DIR / "extracted",
    DATA_DIR / "cleaned",
    DATA_DIR / "selected",
    DATA_DIR / "chunks",
    DATA_DIR / "vector_db",
]
OPTIONAL_TARGETS = {
    "llm_processed": DATA_DIR / "llm_processed",
    "imported_lectures": DATA_DIR / "raw" / "lectures",
}


def _safe_clear_directory(path: Path) -> int:
    root = DATA_DIR.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise RuntimeError(f"Refuse to clear outside backend/data: {resolved}")
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return 0
    if not path.is_dir():
        raise RuntimeError(f"Refuse to clear non-directory: {path}")

    count = 0
    for child in path.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            for nested in sorted(child.rglob("*"), reverse=True):
                if nested.is_file() or nested.is_symlink():
                    nested.unlink()
                    count += 1
                elif nested.is_dir():
                    nested.rmdir()
            child.rmdir()
            count += 1
        else:
            child.unlink()
            count += 1
    (path / ".gitkeep").touch(exist_ok=True)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear generated pipeline outputs safely.")
    parser.add_argument(
        "--include-llm-processed",
        action="store_true",
        help="Also clear backend/data/llm_processed.",
    )
    parser.add_argument(
        "--include-imported-lectures",
        action="store_true",
        help="Also clear backend/data/raw/lectures before re-importing curated raw_temp files.",
    )
    args = parser.parse_args()

    targets = list(DEFAULT_TARGETS)
    if args.include_llm_processed:
        targets.append(OPTIONAL_TARGETS["llm_processed"])
    if args.include_imported_lectures:
        targets.append(OPTIONAL_TARGETS["imported_lectures"])

    for target in targets:
        removed = _safe_clear_directory(target)
        print(f"cleared {target}: removed={removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
