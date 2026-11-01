"""Weekly plan: posting slots per account, format/topic for each slot, and distinct angles."""
import json
import random
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import anthropic

from engine import content, db, llm
from engine.config import env


def posts_per_day(cfg: dict, day: date) -> int:
    weeks_live = (day - cfg["launch_date"]).days // 7
    if weeks_live < 0:
        return 0
    ramp = cfg.get("ramp") or []
    return ramp[weeks_live] if weeks_live < len(ramp) else cfg["posts_per_day"]


def _spread(times: list[str], n: int) -> list[str]:
    """Pick n posting times spread across the day."""
    if n >= len(times):
        return times
    return [times[round(i * len(times) / n)] for i in range(n)]


def slots(cfg: dict, account: dict, start: date, days: int = 7) -> list[datetime]:
    tz = ZoneInfo(cfg["timezone"])
    out = []
    for d in range(days):
        day = start + timedelta(days=d)
        for hhmm in _spread(account["post_times"], posts_per_day(cfg, day)):
            h, m = map(int, hhmm.split(":"))
            out.append(datetime.combine(day, time(h, m), tz).astimezone(ZoneInfo("UTC")))
    return out


def _allocate(weights: dict[str, float], n: int) -> list[str]:
    """n items split by weights (largest remainder), shuffled."""
    total = sum(weights.values())
    exact = {k: n * w / total for k, w in weights.items()}
    counts = {k: int(v) for k, v in exact.items()}
    for k in sorted(exact, key=lambda k: exact[k] - counts[k], reverse=True)[: n - sum(counts.values())]:
        counts[k] += 1
    items = [k for k, c in counts.items() for _ in range(c)]
    random.shuffle(items)
    return items


def mix_for(cfg: dict, account: dict, day: date) -> dict[str, float]:
    """The account's format mix on a given day (format_mix_next applies from format_switch_date)."""
    switch = cfg.get("format_switch_date")
    mix = account.get("format_mix_next") if switch and day >= switch and account.get("format_mix_next") else account["format_mix"]
    return {f: w for f, w in mix.items() if f in cfg["ready_formats"]} or {"carousel": 1}


def assign(cfg: dict, account: dict, slot_times: list[datetime]) -> list[tuple[str, str]]:
    """(format, topic) for each slot; formats follow the mix in force on that slot's day."""
    tz = ZoneInfo(cfg["timezone"])
    by_mix: dict[str, list[int]] = defaultdict(list)
    for i, t in enumerate(slot_times):
        by_mix[json.dumps(mix_for(cfg, account, t.astimezone(tz).date()), sort_keys=True)].append(i)
    formats = [""] * len(slot_times)
    for key, idxs in by_mix.items():
        for i, f in zip(idxs, _allocate(json.loads(key), len(idxs))):
            formats[i] = f
    return list(zip(formats, _allocate(cfg["topic_mix"], len(slot_times))))


def recent_hooks(days: int = 30, limit: int = 80) -> list[str]:
    since = (datetime.now(ZoneInfo("UTC")) - timedelta(days=days)).isoformat()
    rows = db.select("posts", {"created_at": f"gte.{since}", "status": "neq.dropped"},
                     columns="hook", order="created_at.desc", limit=limit)
    return [r["hook"] for r in rows]


def proven_hooks(limit: int = 12) -> list[str]:
    return [w["hook"] for w in winners(limit)]


def winners(limit: int = 6) -> list[dict]:
    """Top-performing hooks (winners and references), best first."""
    return db.select("hooks", {"active": "is.true"}, columns="hook,hook_type,topic,format,views,source",
                     order="views.desc.nullslast", limit=limit)


def plan_angles(topic_counts: Counter, avoid: list[str]) -> dict[str, list[str]]:
    """One quick call that lists distinct angles per topic, so accounts don't write the same post."""
    wanted = "\n".join(f"- {t}: {c} angles ({content.TOPICS[t]})" for t, c in topic_counts.items())
    avoid_text = "\n".join(f"- {h}" for h in avoid[:60]) or "(none yet)"
    schema = content._obj({"topics": {"type": "array", "items": content._obj({
        "topic": {"type": "string", "enum": list(content.TOPICS)},
        "angles": {"type": "array", "items": {"type": "string"}},
    })}})
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    with client.messages.stream(
        model=llm.model_for(fast=False),
        max_tokens=32000,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
        system=content.system_prompt(),
        messages=[{"role": "user", "content": (
            "Plan next week's Instagram posts for 5 founder-education accounts. List distinct post angles "
            "(one specific idea each, one line, not a hook) for each topic below. No two angles may overlap, "
            f"and none may repeat these recent hooks:\n{avoid_text}\n\nAngles needed:\n{wanted}"
        )}],
    ) as stream:
        message = stream.get_final_message()
    text = next(b.text for b in message.content if b.type == "text")
    angles = {t["topic"]: t["angles"] for t in json.loads(text)["topics"]}
    print(f"angles planned (${llm.cost_usd(llm.model_for(False), message.usage):.3f})")
    return angles


SOURCED_KINDS = ("reddit_qa", "breakdown", "india_admin", "funding_roundup")
CAROUSEL_ONLY = ("funding_roundup",)  # one round per slide reads best as a carousel
# Formats that suit each post type (a company breakdown doesn't work as a fake DM chat, etc.)
KIND_FORMATS = {
    "evergreen": None,  # any
    "reddit_qa": None,
    "breakdown": ("carousel", "reaction", "animated", "myth_fact"),
    "india_admin": ("carousel", "reaction", "animated", "checklist"),
    "funding_roundup": ("carousel",),
    "news": ("carousel", "reaction", "animated"),
    "winner": None,
}


def fit_format(account: dict, kind: str, fmt: str, ready: list[str]) -> str:
    """Keep fmt if it suits the post type, else re-pick from the suitable formats by the account's mix."""
    allowed = KIND_FORMATS.get(kind)
    if allowed is None or fmt in allowed:
        return fmt
    mix = {f: w for f, w in {**account["format_mix"], **(account.get("format_mix_next") or {})}.items()
           if f in allowed and f in ready} or {"carousel": 1}
    return random.choices(list(mix), weights=list(mix.values()))[0]


def _fetch_docs(kind: str, count: int, week_start: date) -> list[dict]:
    from engine import sources
    if count <= 0:
        return []
    if kind == "reddit_qa":
        return sources.reddit_questions(count)
    if kind == "breakdown":
        return sources.breakdowns(count)
    if kind == "india_admin":
        return sources.india_topics(count)
    if kind == "funding_roundup":
        doc = sources.funding_roundup(week_start.isoformat())
        return [doc] if doc else []
    return []


def build_week(cfg: dict, start: date, only_slots: dict[str, list[datetime]] | None = None) -> dict:
    """Returns {custom_id: plan entry}. Evergreen entries group slots by (account, format, topic) and carry
    angles; sourced entries are one slot each and carry the real source material ("doc")."""
    from engine import sources
    tz = ZoneInfo(cfg["timezone"])
    roundup_cfg = sources.settings()["funding_roundup"]

    top_winners = winners()
    planned = []  # [account_id, slot, format, topic, kind]
    for account in cfg["accounts"]:
        account_slots = slots(cfg, account, start) if only_slots is None else only_slots.get(account["id"], [])
        n = len(account_slots)
        # Exploit/explore: a fixed share of slots reuse the winning pattern, the rest follow the content mix
        n_win = round(n * cfg.get("exploit_share", 0)) if n and top_winners else 0
        kinds = ["winner"] * n_win + (_allocate(account.get("content_mix") or {"evergreen": 1}, n - n_win) if n else [])
        random.shuffle(kinds)
        rows = [[account["id"], slot, fmt, topic, kind]
                for slot, (fmt, topic), kind in zip(account_slots, assign(cfg, account, account_slots), kinds)]
        if account["id"] == roundup_cfg["account"] and rows:
            day = [r for r in rows if r[1].astimezone(tz).weekday() == roundup_cfg["weekday"]]
            (day or rows)[0][4] = "funding_roundup"
        planned += rows

    # Gather real sources; slots we can't source fall back to evergreen
    wanted = Counter(r[4] for r in planned if r[4] in SOURCED_KINDS)
    docs = {kind: _fetch_docs(kind, count, start) for kind, count in wanted.items()}
    accounts = {a["id"]: a for a in cfg["accounts"]}
    for r in sorted(planned, key=lambda r: r[1]):
        r[2] = fit_format(accounts[r[0]], r[4], r[2], cfg["ready_formats"])
        if r[4] in SOURCED_KINDS:
            r.append(docs[r[4]].pop(0) if docs[r[4]] else None)
            if r[5] is None:
                r[4] = "evergreen"
            elif r[4] in CAROUSEL_ONLY:
                r[2] = "carousel"
    print("kinds planned:", dict(Counter(r[4] for r in planned)))

    plan = {}
    groups: dict[tuple, list[datetime]] = defaultdict(list)
    for i, r in enumerate(planned):
        account_id, slot, fmt, topic, kind = r[:5]
        if kind == "evergreen":
            groups[(account_id, fmt, topic)].append(slot)
        elif kind == "winner":
            key = f"{account_id}__{fmt}__winner"
            entry = plan.setdefault(key, {"account": account_id, "format": fmt, "kind": "winner", "slots": [],
                                          "winners": top_winners})
            entry["slots"].append(slot.isoformat())
        else:
            plan[f"{account_id}__{kind}__{i}"] = {"account": account_id, "format": fmt, "kind": kind,
                                                  "slots": [slot.isoformat()], "doc": r[5]}

    topic_counts = Counter()
    for (_, _, topic), group_slots in groups.items():
        topic_counts[topic] += len(group_slots)
    angles = plan_angles(topic_counts, recent_hooks()) if topic_counts else {}

    pools = {t: list(a) for t, a in angles.items()}
    for (account_id, fmt, topic), group_slots in groups.items():
        group_slots.sort()
        take = [pools[topic].pop(0) if pools.get(topic) else f"a fresh {topic} angle" for _ in group_slots]
        plan[f"{account_id}__{fmt}__{topic}"] = {
            "account": account_id, "format": fmt, "topic": topic, "kind": "evergreen",
            "slots": [s.isoformat() for s in group_slots], "angles": take,
        }
    return plan
