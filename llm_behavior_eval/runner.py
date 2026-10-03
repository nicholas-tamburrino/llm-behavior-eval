"""Run cases against an adapter, score them, and (re)score saved runs."""
import json
from collections import defaultdict

from .checks import score_case

BASE_SEED = 1234


def run_case(case, adapter, run_idx=0):
    """Play every user turn of one case. Returns (replies, check_results)."""
    if hasattr(adapter, "start_case"):
        adapter.start_case(case["id"])
    history, replies = [], []
    for t, user in enumerate(case["turns"]):
        seed = BASE_SEED + run_idx * 100 + t
        reply = adapter(history, user, seed)
        history += [{"role": "user", "content": user}, {"role": "assistant", "content": reply}]
        replies.append(reply)
    return replies, score_case(case, replies)


def run_all(cases, adapter, runs=1, on_progress=None):
    """Returns a list of row dicts, one per (case, run)."""
    rows = []
    for case in cases:
        for run_idx in range(runs):
            replies, results = run_case(case, adapter, run_idx)
            rows.append({
                "id": case["id"], "category": case["category"], "run": run_idx + 1,
                "known_gap": bool(case.get("known_gap")), "turns": case["turns"],
                "replies": replies, "results": results,
                "passed": all(r["passed"] for r in results),
            })
            if on_progress:
                on_progress(rows[-1])
    return rows


def rescore(rows, cases):
    """Re-score saved replies with the current checks (no model needed)."""
    by_id = {c["id"]: c for c in cases}
    out = []
    for row in rows:
        case = by_id.get(row["id"])
        if case is None:
            continue
        results = score_case(case, row["replies"])
        out.append({**row, "known_gap": bool(case.get("known_gap")), "results": results,
                    "passed": all(r["passed"] for r in results)})
    return out


def write_jsonl(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def summarize(rows):
    """Per-category and overall counts. A case passes only if every run of it passed."""
    cases = defaultdict(list)
    for r in rows:
        cases[(r["category"], r["id"])].append(r)
    by_cat = defaultdict(lambda: {"cases": 0, "passed": 0, "unstable": 0})
    for (cat, _), runs in cases.items():
        ok = [r["passed"] for r in runs]
        by_cat[cat]["cases"] += 1
        by_cat[cat]["passed"] += all(ok)
        by_cat[cat]["unstable"] += (any(ok) and not all(ok))
    total = {k: sum(v[k] for v in by_cat.values()) for k in ("cases", "passed", "unstable")}
    return dict(by_cat), total
