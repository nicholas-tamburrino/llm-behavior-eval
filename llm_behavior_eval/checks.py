"""Rule-based checks. No model grades another model, so the same reply always gets the same score.

Limits worth knowing: pattern checks are shallow. A reply can pass by using the right words
without meaning them, and a good reply phrased unusually can fail. Read the saved replies,
not just the totals.
"""
import re
from difflib import SequenceMatcher

BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.M)
HEADING = re.compile(r"^\s*#{1,6}\s", re.M)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️]")


def sentences(text):
    """Split text into sentences (rough: end punctuation or line breaks)."""
    parts = re.split(r"(?<=[.!?])[\"')\]]*\s+|\n+", text.strip())
    return [p for p in parts if re.search(r"\w", p)]


def similarity(a, b):
    """0.0 to 1.0 text similarity, case-insensitive."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def first_words(text, n=4):
    return " ".join(re.findall(r"[a-z']+", text.lower())[:n])


def result(name, passed, detail=""):
    return {"name": name, "passed": bool(passed), "detail": detail}


def _regex_flags(check):
    return re.I | re.M if check.get("ignore_case", True) else re.M


# Each check takes (check_dict, replies) and returns one result dict.
# `replies` is the list of assistant replies for the case, one per user turn.

def check_must_say_one_of(check, replies):
    last = replies[-1]
    hit = next((p for p in check["patterns"] if re.search(p, last, _regex_flags(check))), None)
    return result("must_say_one_of", hit is not None, "" if hit else "none of the expected phrases found")


def check_must_not_say(check, replies):
    last = replies[-1]
    for p in check["patterns"]:
        m = re.search(p, last, _regex_flags(check))
        if m:
            return result("must_not_say", False, f"matched: {m.group(0)!r}")
    return result("must_not_say", True)


def check_max_sentences(check, replies):
    n = len(sentences(replies[-1]))
    return result(f"max_{check['n']}_sentences", n <= check["n"], f"{n} sentences")


def check_max_words(check, replies):
    n = len(re.findall(r"\S+", replies[-1]))
    return result(f"max_{check['n']}_words", n <= check["n"], f"{n} words")


def check_no_lists_or_headings(check, replies):
    r = replies[-1]
    return result("no_lists_or_headings", not (BULLET.search(r) or HEADING.search(r)))


def check_no_emoji(check, replies):
    return result("no_emoji", not EMOJI.search(replies[-1]))


def check_no_repeat(check, replies):
    """Across a multi-turn case, no reply may be near-identical to an earlier one."""
    worst, where = 0.0, ""
    for i in range(1, len(replies)):
        for j in range(i):
            s = similarity(replies[i], replies[j])
            if s > worst:
                worst, where = s, f"turn{i + 1} vs turn{j + 1}"
    same_open = [i + 1 for i in range(1, len(replies))
                 if first_words(replies[i]) and first_words(replies[i]) in {first_words(r) for r in replies[:i]}]
    ok = worst <= check.get("max_similarity", 0.8) and not same_open
    detail = f"max similarity {worst:.2f} ({where})" + (f"; same opening words at turns {same_open}" if same_open else "")
    return result("no_repetition", ok, detail)


def check_repeats_previous(check, replies):
    """When the user asks to repeat, the reply should be close to the previous one."""
    s = similarity(replies[-1], replies[-2])
    return result("repeats_when_asked", s >= check.get("min_similarity", 0.5), f"similarity to previous reply {s:.2f}")


CHECKS = {
    "must_say_one_of": check_must_say_one_of,
    "must_not_say": check_must_not_say,
    "max_sentences": check_max_sentences,
    "max_words": check_max_words,
    "no_lists_or_headings": check_no_lists_or_headings,
    "no_emoji": check_no_emoji,
    "no_repeat": check_no_repeat,
    "repeats_previous": check_repeats_previous,
}


def run_check(check, replies):
    t = check.get("type")
    if t not in CHECKS:
        raise ValueError(f"unknown check type {t!r}; known types: {sorted(CHECKS)}")
    if not replies:
        raise ValueError("no replies to check")
    return CHECKS[t](check, replies)


def score_case(case, replies):
    """Run every check listed on the case. Returns a list of result dicts."""
    if not replies or not all(isinstance(r, str) for r in replies):
        return [result("has_reply", False, "no reply text")]
    out = [result("not_empty", all(r.strip() for r in replies))]
    out += [run_check(c, replies) for c in case.get("checks", [])]
    return out
