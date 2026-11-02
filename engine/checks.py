"""Automatic quality gate for AI-written posts. Returns a list of problems (empty = pass)."""
import re
from difflib import SequenceMatcher

from engine.content import LIMITS, load_facts

BANNED = [
    "guaranteed", "guarantee you", "100%", "will get you funded", "get rich",
    "risk-free", "never fails", "secret investors don't want", "beesz",
]
# Money, percentages and big-number words need a fact sheet source
FACT_NUMBER = re.compile(r"[$₹€£]\s?\d|\d\s?%|\b\d+(\.\d+)?\s?(k|m|bn|million|billion|lakh|crore)\b", re.I)
SIMILAR = 0.8
# Template phrases that make a hook read like AI-written content
AI_HOOK = re.compile(r"^\s*(unpopular opinion|hot take|pov|here's why|let's talk|the truth about)\b|game[- ]changer|"
                     r"in today's world|—", re.I)


def _all_text(post: dict) -> str:
    parts = [post["hook"], post.get("cover_subtitle", ""), post["cta"], post["caption"]]
    for s in post.get("slides", []):
        parts += [s["title"], s["body"]]
    parts += [p["text"] for p in post.get("points", [])]
    parts += [m["text"] for m in post.get("messages", [])]
    parts += [x for p in post.get("pairs", []) for x in (p["myth"], p["fact"])]
    parts += post.get("items", [])
    for b in post.get("beats", []):
        v = b.get("visual") or {}
        parts += [b["say"], v.get("title", ""), v.get("value", ""), v.get("label", ""), *(v.get("items") or [])]
    return "\n".join(parts)


def _too_long(problems: list[str], name: str, value: str, limit: int) -> None:
    if not value.strip():
        problems.append(f"{name} is empty")
    elif len(value) > limit:
        problems.append(f"{name} too long ({len(value)}>{limit})")


NUMBER = re.compile(r"\d[\d,.]*")
MONEY = re.compile(r"[$₹€£]\s?(\d[\d,.]*)|(\d[\d,.]*)\s?(?:%|percent|lakh|crore|cr\b|k\b|bn\b|million|billion)", re.I)


def _ungrounded_numbers(post: dict, sources: list[str], min_agree: int = 1) -> list[str]:
    """Numbers in the post (other than small counts) found in fewer than min_agree of the sources."""
    plains = [s.replace(",", "") for s in sources]
    text = _all_text(post)
    # Money, percentages and amounts are always checked; other numbers only if they aren't small counts
    always = {m.group(1) or m.group(2) for m in MONEY.finditer(text)}
    missing = []
    for raw in NUMBER.findall(text):
        n = raw.replace(",", "").rstrip(".")
        if not n:
            continue
        whole = re.compile(rf"(?<![\d.]){re.escape(n)}(?![\d])")
        if (raw in always or len(n) > 2 or "." in n) and sum(bool(whole.search(p)) for p in plains) < min_agree:
            missing.append(raw)
    return missing


def check_post(post: dict, fmt: str = "carousel", recent_hooks: list[str] = (),
               source_text: str | None = None, source_texts: list[str] | None = None,
               min_agree: int = 1) -> list[str]:
    """source_text(s): for sourced posts (news, Reddit, breakdowns, India guides) the material that replaces
    the fact sheet. min_agree: how many sources must contain each figure (2 for India guides)."""
    if source_text is not None:
        source_texts = [source_text]
    problems = []
    limits = LIMITS[fmt]
    for field in ("hook", "cta", "caption"):
        _too_long(problems, field, post[field], limits[field])

    if fmt == "carousel":
        _too_long(problems, "cover_subtitle", post["cover_subtitle"], limits["cover_subtitle"])
        if not 4 <= len(post["slides"]) <= 7:
            problems.append(f"needs 4-7 slides, got {len(post['slides'])}")
        for i, s in enumerate(post["slides"], 1):
            _too_long(problems, f"slide {i} title", s["title"], limits["slide_title"])
            _too_long(problems, f"slide {i} body", s["body"], limits["slide_body"])
    elif fmt in ("reaction", "animated"):
        lo, hi = (3, 5) if fmt == "reaction" else (3, 3)
        if not lo <= len(post["points"]) <= hi:
            problems.append(f"needs {lo}-{hi} points, got {len(post['points'])}")
        for i, p in enumerate(post["points"], 1):
            _too_long(problems, f"point {i}", p["text"], limits["point"])
    elif fmt == "chat":
        _too_long(problems, "other_role", post["other_role"], limits["role"])
        if not 5 <= len(post["messages"]) <= 6:
            problems.append(f"needs 5-6 messages, got {len(post['messages'])}")
        for i, m in enumerate(post["messages"], 1):
            _too_long(problems, f"message {i}", m["text"], limits["message"])
    elif fmt == "myth_fact":
        if not len(post["pairs"]) == 2:
            problems.append(f"needs 2 myth/fact pairs, got {len(post['pairs'])}")
        for i, p in enumerate(post["pairs"], 1):
            _too_long(problems, f"myth {i}", p["myth"], limits["myth"])
            _too_long(problems, f"fact {i}", p["fact"], limits["fact"])
    elif fmt == "explainer":
        if not 5 <= len(post["beats"]) <= 7:
            problems.append(f"needs 5-7 beats, got {len(post['beats'])}")
        for i, b in enumerate(post["beats"], 1):
            _too_long(problems, f"beat {i}", b["say"], limits["say"])
            if len(str((b.get("visual") or {}).get("value", ""))) > 14:
                problems.append(f"beat {i} visual value too long")
    elif fmt == "checklist":
        if not 4 <= len(post["items"]) <= 5:
            problems.append(f"needs 4-5 items, got {len(post['items'])}")
        for i, item in enumerate(post["items"], 1):
            _too_long(problems, f"item {i}", item, limits["item"])

    if AI_HOOK.search(post["hook"]):
        problems.append("hook reads like an AI template (e.g. 'Unpopular opinion:'); write it like a real reaction")
    if not 3 <= len(post["hashtags"]) <= 8:
        problems.append("needs 3-8 hashtags")

    text = _all_text(post).lower()
    for phrase in BANNED:
        if phrase in text:
            problems.append(f"banned phrase: {phrase!r}")

    if source_texts is not None:
        missing = _ungrounded_numbers(post, source_texts, min(min_agree, len(source_texts)))
        if missing:
            problems.append(f"numbers not backed by {'2+ sources' if min_agree > 1 else 'the source'}: {missing[:5]}")
    else:
        fact_ids = {f["id"] for f in load_facts()}
        unknown = set(post["facts_used"]) - fact_ids
        if unknown:
            problems.append(f"cites unknown facts: {sorted(unknown)}")
        if FACT_NUMBER.search(_all_text(post)) and not post["facts_used"]:
            problems.append("uses money/percent figures without a fact sheet source")

    for old in recent_hooks:
        if SequenceMatcher(None, post["hook"].lower(), old.lower()).ratio() >= SIMILAR:
            problems.append(f"hook too similar to recent: {old!r}")
            break
    return problems
