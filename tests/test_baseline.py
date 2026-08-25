"""Regression checks for the isolated comparison baseline."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from run_baseline import evaluate_baseline, load_cases


class BaselineTests(unittest.TestCase):
    def test_uses_the_twenty_final_evaluation_cases(self) -> None:
        self.assertEqual(len(load_cases()), 20)

    def test_results_are_deterministic_and_have_category_totals(self) -> None:
        first = evaluate_baseline()
        second = evaluate_baseline()
        self.assertEqual(first, second)
        self.assertEqual(first["total"], len(first["results"]))
        self.assertEqual(sum(category["total"] for category in first["categories"].values()), first["total"])
