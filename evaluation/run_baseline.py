"""Run the isolated early extractive baseline against the final evaluator's cases."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from baseline_agent import ExtractiveBaseline
from run_eval import evaluate_case


def load_cases() -> list[dict]:
    visible = json.loads((ROOT / "evaluation" / "visible-cases.json").read_text(encoding="utf-8"))["cases"]
    original = json.loads((ROOT / "evaluation" / "original-cases.json").read_text(encoding="utf-8"))["cases"]
    return visible + original


def evaluate_baseline() -> dict:
    agent = ExtractiveBaseline(ROOT)
    results = []
    category_totals: Counter[str] = Counter()
    category_passed: Counter[str] = Counter()
    for case in load_cases():
        passed, errors = evaluate_case(agent, case)
        category = case["category"]
        category_totals[category] += 1
        category_passed[category] += int(passed)
        results.append({"id": case["id"], "category": category, "passed": passed, "errors": errors})
    return {
        "label": "early/simple extractive baseline (not a production system)",
        "method": "one raw lexical top passage; existing sanitized order lookup when an order ID is present; no session memory or policy-specific handling",
        "results": results,
        "passed": sum(item["passed"] for item in results),
        "total": len(results),
        "categories": {
            category: {"passed": category_passed[category], "total": category_totals[category]}
            for category in sorted(category_totals)
        },
    }


def main() -> int:
    result = evaluate_baseline()
    output_path = ROOT / "evaluation" / "baseline-results.json"
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
