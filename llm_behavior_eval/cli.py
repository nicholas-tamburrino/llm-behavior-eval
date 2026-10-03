"""Command line: `python -m llm_behavior_eval run ...` and `... rescore ...`."""
import argparse
import sys
from datetime import datetime
from pathlib import Path

from .adapters import FixtureAdapter, OllamaAdapter, OpenAICompatAdapter
from .cases import CaseError, load_cases
from .report import render_markdown
from .runner import read_jsonl, rescore, run_all, write_jsonl


def build_parser():
    p = argparse.ArgumentParser(prog="llm_behavior_eval", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run cases against a model or saved fixture replies")
    r.add_argument("--cases", required=True, help="path to a JSON case file")
    r.add_argument("--adapter", choices=["fixture", "ollama", "openai"], required=True)
    r.add_argument("--model", help="model name (ollama / openai adapters)")
    r.add_argument("--system-file", help="text file with the system prompt the assistant should follow")
    r.add_argument("--fixtures", help="JSONL of saved replies (fixture adapter)")
    r.add_argument("--base-url", default="https://api.openai.com/v1", help="OpenAI-compatible base URL")
    r.add_argument("--api-key-env", default="OPENAI_API_KEY", help="env var holding the API key")
    r.add_argument("--category", help="only run one category")
    r.add_argument("--runs", type=int, default=1, help="runs per case (different seeds)")
    r.add_argument("--out", help="report path (.md); a matching .jsonl is written beside it")
    r.add_argument("--title", default="Behavior evaluation")

    s = sub.add_parser("rescore", help="re-score a saved .jsonl run with the current checks")
    s.add_argument("jsonl")
    s.add_argument("--cases", required=True)
    s.add_argument("--out", help="report path (.md)")
    s.add_argument("--title", default="Behavior evaluation (re-scored)")
    return p


def _adapter(args):
    system = Path(args.system_file).read_text(encoding="utf-8") if args.system_file else ""
    if args.adapter == "fixture":
        if not args.fixtures:
            raise SystemExit("--fixtures is required for the fixture adapter")
        return FixtureAdapter(args.fixtures)
    if not args.model:
        raise SystemExit("--model is required for this adapter")
    if args.adapter == "ollama":
        return OllamaAdapter(args.model, system)
    return OpenAICompatAdapter(args.model, system, args.base_url, args.api_key_env)


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        cases = load_cases(args.cases, getattr(args, "category", None))
    except (CaseError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.cmd == "run":
        adapter = _adapter(args)
        rows = run_all(cases, adapter, args.runs,
                       on_progress=lambda r: print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['id']}", file=sys.stderr))
        meta = {"Adapter": args.adapter, "Model": args.model or ("none: hand-written fixture replies that exercise the scorer, not model output" if args.adapter == "fixture" else "n/a"), "Runs per case": args.runs}
    else:
        rows = rescore(read_jsonl(args.jsonl), cases)
        meta = {"Source": args.jsonl}
    report = render_markdown(rows, args.title, meta)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        write_jsonl(rows, str(Path(args.out).with_suffix(".jsonl")))
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(report)
    return 0 if all(r["passed"] or r["known_gap"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
