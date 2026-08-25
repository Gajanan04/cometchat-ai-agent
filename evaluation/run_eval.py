"""Deterministic behavior evaluation for supplied and original cases."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.agent.agent import SupportAgent


def _concept_present(answer: str, concept: str) -> bool:
    text = answer.lower().replace("–", "-")
    concept = concept.lower().replace("–", "-")
    groups = {
        "report within 7 days": ["within 7 days"],
        "final sale does not block damaged-item review": ["final sale does not block", "damaged-item review"],
        "human review before approval": ["human review", "before"],
        "canada is supported": ["canada is supported"],
        "shipping to germany is not currently available": ["shipping to germany is not currently available"],
        "the order is cancelled": ["order is cancelled"],
        "it will not be shipped": ["will not be shipped"],
        "order was not found": ["order was not found"],
        "check the order id or contact support": ["check the order id", "contact support"],
        "shipped with canada post": ["shipped with canada post"],
        "delivery estimate is unavailable": ["delivery estimate is unavailable"],
        "no lifetime warranty": ["does not offer a lifetime warranty"],
        "bags have 2 years": ["bags and backpacks have a 2-year"],
        "drinkware and travel accessories have 1 year": ["drinkware and travel accessories have a 1-year"],
        "migration note is not authoritative": ["migration note is not authoritative"],
        "standard policy is 30 days unless a valid exception applies": ["standard policy is 30 calendar days", "valid exception"],
        "the agent cannot approve a return": ["can’t approve a return"],
        "the supplied information is insufficient": ["supplied information is insufficient"],
        "human confirmation": ["human support"],
        "current official sources conflict": ["current official sources conflict"],
        "one says hand-wash the body": ["hand-wash the breeze tumbler body"],
        "one says all components are dishwasher safe": ["all components are dishwasher safe"],
        "human confirmation or safest interim guidance": ["safest interim guidance"],
    }
    return all(token in text for token in groups.get(concept, [concept]))


def evaluate_case(agent: SupportAgent, case: dict) -> tuple[bool, list[str]]:
    session_id = f"eval-{case['id']}"
    response = None
    for message in case["messages"]:
        response = agent.chat(session_id, message["content"])
    assert response is not None
    expect = case["expect"]
    errors: list[str] = []
    for term in expect.get("must_include", []) + expect.get("must_include_concepts", []):
        if not _concept_present(response.answer, term): errors.append(f"missing: {term}")
    for term in expect.get("must_not_include", []) + expect.get("must_not_invent", []):
        if term.lower() in response.answer.lower(): errors.append(f"forbidden: {term}")
    required = set(expect.get("required_sources", []))
    actual = {source.filename for source in response.sources}
    if not required <= actual: errors.append(f"sources: expected {required}, got {actual}")
    tool = expect.get("tool")
    if tool == "order_lookup" and not response.tool_calls: errors.append("order lookup not called")
    if tool == "not_called" and response.tool_calls: errors.append("unexpected tool call")
    if "handoff" in expect and response.handoff["recommended"] != expect["handoff"]: errors.append("handoff mismatch")
    return not errors, errors


def main() -> int:
    visible = json.loads((ROOT / "evaluation" / "visible-cases.json").read_text(encoding="utf-8"))["cases"]
    original = json.loads((ROOT / "evaluation" / "original-cases.json").read_text(encoding="utf-8"))["cases"]
    agent = SupportAgent(ROOT)
    results = []
    categories: Counter[str] = Counter()
    for case in visible + original:
        passed, errors = evaluate_case(agent, case)
        categories[case["category"]] += int(passed)
        results.append({"id": case["id"], "category": case["category"], "passed": passed, "errors": errors})
    print(json.dumps({"results": results, "passed": sum(item["passed"] for item in results), "total": len(results), "categories": dict(categories)}, indent=2))
    return 0 if all(item["passed"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
