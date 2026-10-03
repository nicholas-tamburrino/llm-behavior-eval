"""Markdown report: summary table, then every failing check with the reply that caused it."""
from datetime import date

from .runner import summarize


def _one_line(text):
    return " \u23ce ".join(part.strip() for part in text.strip().splitlines() if part.strip())


def render_markdown(rows, title, meta=None):
    by_cat, total = summarize(rows)
    lines = [f"# {title}", ""]
    for k, v in (meta or {}).items():
        lines.append(f"- **{k}:** {v}")
    lines += ["", f"Date: {date.today().isoformat()}", "",
              f"**Result: {total['passed']} of {total['cases']} cases passed**"
              + (f" ({total['unstable']} unstable across runs)" if total["unstable"] else ""), "",
              "| Category | Cases | Passed | Unstable |", "| --- | ---: | ---: | ---: |"]
    for cat in sorted(by_cat):
        c = by_cat[cat]
        lines.append(f"| {cat} | {c['cases']} | {c['passed']} | {c['unstable']} |")
    failed = [r for r in rows if not r["passed"]]
    lines += ["", "## Failures", ""]
    if not failed:
        lines.append("None.")
    for r in failed:
        gap = " (marked known gap)" if r["known_gap"] else ""
        lines.append(f"### {r['id']} (run {r['run']}){gap}")
        for i, (user, reply) in enumerate(zip(r["turns"], r["replies"]), 1):
            lines.append(f"- Turn {i} user: {_one_line(user)}")
            lines.append(f"- Turn {i} reply: {_one_line(reply)}")
        for res in r["results"]:
            if not res["passed"]:
                lines.append(f"- FAILED `{res['name']}`" + (f": {res['detail']}" if res["detail"] else ""))
        lines.append("")
    lines += ["## How to read this", "",
              "Checks are rule-based patterns, so the same reply always scores the same. They are shallow: "
              "read the failing replies above, and spot-read a few passing ones, before trusting the totals.", ""]
    return "\n".join(lines)
