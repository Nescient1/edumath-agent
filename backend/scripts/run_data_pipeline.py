import argparse
import subprocess
import sys
from pathlib import Path


SCRIPTS = [
    "prepare_raw_temp.py",
    "extract_text.py",
    "clean_text.py",
    "classify_chunks.py",
    "build_chunks.py",
    "embed_to_chroma.py",
    "retrieval_test.py",
]


def run_script(script_name: str) -> None:
    script_path = Path(__file__).resolve().parent / script_name
    print(f"\n=== Running {script_name} ===")
    result = subprocess.run([sys.executable, str(script_path)], check=False)
    if result.returncode != 0:
        raise SystemExit(f"{script_name} failed with exit code {result.returncode}.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-prepare", action="store_true")
    parser.add_argument("--skip-extract", action="store_true")
    args = parser.parse_args()

    scripts = SCRIPTS
    if args.skip_prepare:
        scripts = [script for script in scripts if script != "prepare_raw_temp.py"]
    if args.skip_extract:
        scripts = [script for script in scripts if script != "extract_text.py"]
    for script in scripts:
        run_script(script)

    print("\nPipeline completed.")


if __name__ == "__main__":
    main()
