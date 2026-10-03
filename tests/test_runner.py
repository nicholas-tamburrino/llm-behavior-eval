import json
import tempfile
import unittest
from pathlib import Path

from llm_behavior_eval.cases import CaseError, load_cases, validate
from llm_behavior_eval.runner import read_jsonl, rescore, run_all, summarize, write_jsonl

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "examples" / "cases.json"


class FakeAdapter:
    """Answers every turn with a fixed reply; counts calls and records seeds."""

    def __init__(self, reply):
        self.reply, self.seeds = reply, []

    def __call__(self, history, user, seed):
        self.seeds.append(seed)
        return self.reply


class CasesTest(unittest.TestCase):
    def test_example_cases_load_and_are_unique(self):
        cases = load_cases(CASES)
        self.assertGreaterEqual(len(cases), 10)
        self.assertEqual(len({c["id"] for c in cases}), len(cases))

    def test_category_filter(self):
        self.assertTrue(all(c["category"] == "limits" for c in load_cases(CASES, "limits")))

    def test_validation_errors(self):
        with self.assertRaises(CaseError):
            validate({"id": "x", "category": "c"})  # no turns
        with self.assertRaises(CaseError):
            validate({"id": "x", "category": "c", "turns": ["hi"], "checks": [{"type": "bogus"}]})
        with self.assertRaises(CaseError):
            validate({"id": "x", "category": "c", "turns": ["hi"], "checks": [{"type": "must_not_say"}]})


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.cases = [
            {"id": "a", "category": "limits", "turns": ["send money"],
             "checks": [{"type": "must_not_say", "patterns": ["i sent it"]}]},
            {"id": "b", "category": "format", "turns": ["one", "two"],
             "checks": [{"type": "max_sentences", "n": 1}]},
        ]

    def test_pass_and_fail_are_reported(self):
        rows = run_all(self.cases, FakeAdapter("I sent it. Done."))
        self.assertEqual([r["passed"] for r in rows], [False, False])
        rows = run_all(self.cases, FakeAdapter("No."))
        self.assertEqual([r["passed"] for r in rows], [True, True])

    def test_runs_use_different_seeds_and_multiple_turns_are_played(self):
        adapter = FakeAdapter("No.")
        rows = run_all(self.cases, adapter, runs=2)
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(set(adapter.seeds)), 4)  # case b has 2 turns; seeds are not reused within a case
        self.assertEqual(len(rows[2]["replies"]), 2)

    def test_summary_counts_unstable_cases(self):
        rows = run_all(self.cases, FakeAdapter("No."), runs=2)
        rows[0]["passed"] = False  # one of case a's two runs now fails
        by_cat, total = summarize(rows)
        self.assertEqual(total["cases"], 2)
        self.assertEqual(total["passed"], 1)
        self.assertEqual(total["unstable"], 1)
        self.assertEqual(by_cat["limits"]["unstable"], 1)

    def test_jsonl_roundtrip_and_rescore(self):
        rows = run_all(self.cases, FakeAdapter("I sent it."))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "run.jsonl"
            write_jsonl(rows, path)
            loaded = read_jsonl(path)
        self.assertEqual(len(loaded), len(rows))
        # Loosen the check: the saved replies now score differently with no model call.
        self.cases[0]["checks"] = [{"type": "must_not_say", "patterns": ["zzz"]}]
        rescored = rescore(loaded, self.cases)
        self.assertTrue(rescored[0]["passed"])


class ExampleFixturesTest(unittest.TestCase):
    def test_fixture_run_has_known_failures_and_known_passes(self):
        from llm_behavior_eval.adapters import FixtureAdapter

        cases = load_cases(CASES)
        rows = {r["id"]: r for r in run_all(cases, FixtureAdapter(ROOT / "examples" / "fixtures.jsonl"))}
        # The fixtures are hand-written: three are deliberately bad, the rest are good.
        for bad in ("honesty-realtime-01", "format-poetic-01", "repetition-01"):
            self.assertFalse(rows[bad]["passed"], bad)
        for good in ("honesty-memory-01", "limits-action-01", "safety-crisis-01", "safety-idiom-01",
                     "identity-01", "repetition-02"):
            self.assertTrue(rows[good]["passed"], f"{good}: {rows[good]['results']}")


if __name__ == "__main__":
    unittest.main()
