import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.rag_service import retrieve_context


QUERY = "我只会求导但不会判断单调区间"


def main() -> None:
    results = retrieve_context(QUERY, k=5)
    print(f"Query: {QUERY}")
    print(f"Retrieved {len(results)} result(s)")
    print("-" * 60)
    for index, result in enumerate(results, start=1):
        print(f"[Result {index}]")
        print(result)
        print("-" * 60)

    joined = "\n".join(results)
    if "导数与函数单调性" in joined or "derivative_monotonicity" in joined:
        print("PASS: retrieved derivative monotonicity related context.")
    else:
        raise SystemExit("FAIL: derivative monotonicity context was not retrieved.")


if __name__ == "__main__":
    main()
