"""Weekly performance review: scorecard vs benchmarks every week; when we're behind, a diagnosis,
content suggestions and rendered sample posts on Telegram. Suggestions are never applied automatically.

Run: python -m scripts.weekly_review           # normal weekly run
     python -m scripts.weekly_review --force   # always include suggestions and samples
"""
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

import anthropic
import yaml

from engine import checks, content, db, llm, produce, telegram
from engine.config import ROOT, env, load_accounts

NOW = datetime.now(timezone.utc)


def bench_cfg() -> dict:
    return yaml.safe_load((ROOT / "config" / "benchmarks.yaml").read_text())


def targets(cfg: dict, accounts_cfg: dict) -> tuple[int, dict]:
    week = (NOW.date() - accounts_cfg["launch_date"]).days // 7 + 1
    phase = next(p for p in cfg["phases"] if week <= p["until_week"])
    return week, phase


def latest_metrics(post_ids: list[str]) -> dict[str, dict]:
    latest = {}
    for i in range(0, len(post_ids), 80):
        ids = ",".join(post_ids[i:i + 80])
        for m in db.select("metrics", {"post_id": f"in.({ids})"}, order="captured_at.asc"):
            latest[m["post_id"]] = m
    return latest


def window_posts(days_from: int, days_to: int) -> list[dict]:
    """Published posts from days_from to days_to ago, each with its latest metrics."""
    start, end = (NOW - timedelta(days=days_from)).isoformat(), (NOW - timedelta(days=days_to)).isoformat()
    posts = db.select("posts", {"status": "eq.published", "and": f"(published_at.gte.{start},published_at.lt.{end})"},
                      columns="id,account_id,format,kind,topic,hook_type,hook,published_at")
    metrics = latest_metrics([p["id"] for p in posts])
    return [{**p, **{k: metrics[p["id"]].get(k) for k in ("views", "reach", "saves", "shares", "skip_rate",
                                                           "avg_watch_time_ms", "follows")}}
            for p in posts if p["id"] in metrics]


def followers_gained(account_id: str, days_ago_end: int) -> int | None:
    end = NOW - timedelta(days=days_ago_end)
    start = end - timedelta(days=7)
    rows = db.select("account_stats", {"account_id": f"eq.{account_id}",
                                       "and": f"(captured_at.gte.{(start - timedelta(days=1)).isoformat()},"
                                              f"captured_at.lte.{end.isoformat()})"},
                     columns="followers,captured_at", order="captured_at.asc")
    if len(rows) < 2:
        return None
    return (rows[-1]["followers"] or 0) - (rows[0]["followers"] or 0)


def _med(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return median(values) if values else None


def account_stats(posts: list[dict], account_id: str, followers: int | None) -> dict:
    mine = [p for p in posts if p["account_id"] == account_id]
    reels = [p for p in mine if p["format"] != "carousel"]
    carousels = [p for p in mine if p["format"] == "carousel"]
    reach = sum(p["reach"] or 0 for p in mine)
    return {
        "posts": len(mine),
        "reel_median_views": _med([p["views"] for p in reels]) if reels else None,
        "carousel_median_views": _med([p["views"] for p in carousels]) if carousels else None,
        "followers_gained": followers,
        "save_share_rate": (sum((p["saves"] or 0) + (p["shares"] or 0) for p in mine) / reach) if reach else None,
        "reel_skip_rate_max": _med([p["skip_rate"] for p in reels]) if reels else None,
    }


def misses(stats: dict, target: dict) -> list[str]:
    out = []
    for key in ("reel_median_views", "carousel_median_views", "followers_gained", "save_share_rate"):
        if stats[key] is not None and stats[key] < target[key]:
            out.append(key)
    if stats["reel_skip_rate_max"] is not None and stats["reel_skip_rate_max"] > target["reel_skip_rate_max"]:
        out.append("reel_skip_rate_max")
    return out


def breakdown(posts: list[dict], key: str) -> dict:
    groups = defaultdict(list)
    for p in posts:
        groups[p.get(key) or "?"].append(p["views"] or 0)
    return {k: {"posts": len(v), "median_views": median(v)} for k, v in groups.items()}


def fmt_val(key: str, v) -> str:
    if v is None:
        return "–"
    if key == "save_share_rate":
        return f"{v * 100:.1f}%"
    if key == "reel_skip_rate_max":
        return f"{v:.0f}%"
    return f"{v:.0f}"


LABELS = {"reel_median_views": "Reel views", "carousel_median_views": "Carousel views",
          "followers_gained": "New followers", "save_share_rate": "Saves+shares", "reel_skip_rate_max": "Reel skip"}


def analyse(acc_cfg: dict, week: int, target: dict, this_week: list[dict], scorecard: dict) -> dict:
    accounts = {a["id"]: a for a in acc_cfg["accounts"]}
    ranked = sorted(this_week, key=lambda p: p["views"] or 0, reverse=True)
    data = {
        "weeks_since_launch": week, "targets": target, "scorecard": scorecard,
        "by_kind": breakdown(this_week, "kind"), "by_format": breakdown(this_week, "format"),
        "by_hook_type": breakdown(this_week, "hook_type"), "by_topic": breakdown(this_week, "topic"),
        "top_posts": [{k: p[k] for k in ("account_id", "format", "kind", "hook", "views", "skip_rate")} for p in ranked[:6]],
        "bottom_posts": [{k: p[k] for k in ("account_id", "format", "kind", "hook", "views")} for p in ranked[-6:]],
        "accounts": {a: {"persona": v["persona"], "content_mix": v.get("content_mix"),
                         "format_mix": v["format_mix"]} for a, v in accounts.items()},
        "ready_formats": acc_cfg["ready_formats"],
    }
    schema = content._obj({
        "diagnosis": {"type": "string"},
        "working": {"type": "array", "items": {"type": "string"}},
        "not_working": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": content._obj({
            "title": {"type": "string"}, "why": {"type": "string"},
            "account": {"type": "string", "enum": list(accounts)},
            "format": {"type": "string", "enum": acc_cfg["ready_formats"]},
            "topic": {"type": "string", "enum": list(content.TOPICS)},
            "sample_angle": {"type": "string"},
        })},
        "mix_changes": {"type": "array", "items": content._obj({
            "account": {"type": "string", "enum": list(accounts)}, "change": {"type": "string"}})},
    })
    prompt = (
        "You are the growth strategist for 5 faceless Instagram accounts that educate early-stage founders "
        "(mostly in India). Here is this week's data vs our benchmarks. Diagnose what is and isn't working, "
        "grounded in the numbers (no generic advice). Then suggest 3-5 content ideas we should ADD or change, "
        "each tied to evidence in the data, with one concrete sample angle we can write right now in a format we "
        "can already produce. Rules: no invented stories or characters; ideas must be relevant and useful to real "
        "founders. mix_changes: specific content_mix/format_mix shifts per account, if the data supports them. "
        "Keep diagnosis under 5 sentences.\n\nDATA:\n" + json.dumps(data, default=str)
    )
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    with client.messages.stream(
        model=llm.model_for(fast=False), max_tokens=32000,
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()
    return json.loads(next(b.text for b in message.content if b.type == "text"))


def send_samples(acc_cfg: dict, suggestions: list[dict], count: int) -> None:
    accounts = {a["id"]: a for a in acc_cfg["accounts"]}
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    for n, s in enumerate(suggestions[:count], 1):
        account = accounts[s["account"]]
        params = content.request_params(llm.model_for(fast=False), account, s["topic"], 1, fmt=s["format"],
                                        angles=[s["sample_angle"]])
        with client.messages.stream(**params) as stream:
            posts = content.parse_posts(stream.get_final_message())
        if not posts:
            continue
        post = posts[0]
        problems = checks.check_post(post, s["format"])
        row = {"id": f"sample-{n}", "content": post, "format": s["format"]}
        try:
            files, _ = produce.render(row, account)
        except Exception as e:
            telegram.send_message(f"Sample {n} ({s['title']}) failed to render: {e}")
            continue
        header = f"🧪 Sample {n}: {s['title']} · @{account['handle']} ({s['format']})"
        if problems:
            header += f"\n⚠️ checks: {'; '.join(problems)}"
        telegram.send_message(header)
        if s["format"] == "carousel":
            telegram.send_photos(files, post["caption"])
        else:
            telegram.send_video(files[0], post["caption"])
        shutil.rmtree(produce.WORK / row["id"], ignore_errors=True)


def main() -> None:
    cfg, acc_cfg = bench_cfg(), load_accounts()
    week, target = targets(cfg, acc_cfg)
    this_week, last_week = window_posts(8, 1), window_posts(15, 8)
    accounts = acc_cfg["accounts"]

    scorecard, flagged, flagged_twice = {}, [], []
    for a in accounts:
        now_stats = account_stats(this_week, a["id"], followers_gained(a["id"], 1))
        prev_stats = account_stats(last_week, a["id"], followers_gained(a["id"], 8))
        missed = misses(now_stats, target)
        scorecard[a["id"]] = {**now_stats, "missed": missed}
        if len(missed) >= cfg["account_misses_to_flag"]:
            flagged.append(a["id"])
            if prev_stats["posts"] and len(misses(prev_stats, target)) >= cfg["account_misses_to_flag"]:
                flagged_twice.append(a["id"])

    views_now = _med([p["views"] for p in this_week])
    views_prev = _med([p["views"] for p in last_week])
    dropped = bool(views_now is not None and views_prev and views_now < views_prev * (1 - cfg["rework_when_views_drop"]))
    rework = len(flagged) >= cfg["rework_when_accounts_flagged"] or dropped or bool(flagged_twice)

    handles = {a["id"]: a["handle"] for a in accounts}
    lines = [f"📈 Weekly review · week {week} since launch · {len(this_week)} posts measured",
             f"Median views per post: {fmt_val('x', views_now)} (previous week {fmt_val('x', views_prev)})", ""]
    for acc_id, s in scorecard.items():
        status = "🔴" if acc_id in flagged else "🟢"
        parts = [f"{LABELS[k]} {fmt_val(k, s[k])}{'✗' if k in s['missed'] else ''}" for k in LABELS]
        lines.append(f"{status} @{handles[acc_id]} ({s['posts']} posts): " + " · ".join(parts))
    lines.append("\nTargets this phase: " + " · ".join(f"{LABELS[k]} {fmt_val(k, target[k])}" for k in LABELS))
    if flagged_twice:
        lines.append("⚠️ Behind 2 weeks in a row: " + ", ".join(f"@{handles[a]}" for a in flagged_twice))
    lines.append("\nVerdict: " + ("REWORK SUGGESTED, details below" if rework else "on track, no changes needed"))
    report = "\n".join(lines)
    print(report)
    telegram.send_message(report)

    if not (rework or "--force" in sys.argv) or not this_week:
        return
    result = analyse(acc_cfg, week, target, this_week, scorecard)
    msg = ["🧠 What the data says", result["diagnosis"], "", "Working:"] + [f"• {w}" for w in result["working"]]
    msg += ["", "Not working:"] + [f"• {w}" for w in result["not_working"]]
    msg += ["", "Suggested content to add:"]
    msg += [f"{i}. {s['title']} (@{handles[s['account']]}, {s['format']}): {s['why']}"
            for i, s in enumerate(result["suggestions"], 1)]
    if result["mix_changes"]:
        msg += ["", "Suggested mix changes:"] + [f"• @{handles[m['account']]}: {m['change']}" for m in result["mix_changes"]]
    msg += ["", "Nothing changes until you approve. Reply in Claude with the numbers you want."]
    print("\n".join(msg))
    telegram.send_message("\n".join(msg))
    send_samples(acc_cfg, result["suggestions"], cfg["sample_posts"])


if __name__ == "__main__":
    main()
