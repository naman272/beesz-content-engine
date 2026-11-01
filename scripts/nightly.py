"""Nightly: collect views, mark winners (their hooks feed next week's plan), daily report,
refresh Instagram tokens, clean old media.

Run: python -m scripts.nightly
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median


from engine import db, instagram, storage, telegram
from engine.config import load_accounts

WINNER_VIEWS = 1000
WINNER_WINDOW_HOURS = 80     # judge within ~72h of publishing
RELATIVE_WINNER = 3          # or 3x the account's median views
MEDIA_KEEP_DAYS = 14


HANDLES = {a["id"]: a["handle"] for a in load_accounts()["accounts"]}


def now() -> datetime:
    return datetime.now(timezone.utc)


def collect_metrics() -> list[dict]:
    since = (now() - timedelta(days=8)).isoformat()
    posts = db.select("posts", {"status": "eq.published", "published_at": f"gte.{since}"})
    rows = []
    for p in posts:
        try:
            m = instagram.insights(p["account_id"], p["ig_media_id"], p["format"])
        except instagram.RateLimited as e:
            print(f"insights paused, Meta limit reached after {len(rows)} posts: {e}")
            break
        except Exception as e:
            print(f"insights failed for {p['id']}: {e}")
            continue
        hours = (now() - datetime.fromisoformat(p["published_at"])).total_seconds() / 3600
        row = {
            "post_id": p["id"], "hours_live": round(hours, 1),
            "views": m.get("views"), "reach": m.get("reach"), "likes": m.get("likes"),
            "comments": m.get("comments"), "saves": m.get("saved"), "shares": m.get("shares"),
            "reposts": m.get("reposts"), "total_interactions": m.get("total_interactions"),
            "profile_visits": m.get("profile_visits"), "profile_activity": m.get("profile_activity"),
            "follows": m.get("follows"), "avg_watch_time_ms": m.get("ig_reels_avg_watch_time"),
            "total_watch_time_ms": m.get("ig_reels_video_view_total_time"),
            "skip_rate": m.get("reels_skip_rate"), "raw": m,
        }
        rows.append({**row, "post": p})
    if rows:
        db.insert("metrics", [{k: v for k, v in r.items() if k != "post"} for r in rows])
    return rows


def collect_account_stats(cfg: dict) -> list[str]:
    lines = []
    for account in cfg["accounts"]:
        try:
            s = instagram.account_stats(account["id"])
            db.insert("account_stats", {"account_id": account["id"], "followers": s.get("followers_count"),
                                        "follows": s.get("follows_count"), "media_count": s.get("media_count")})
            lines.append(f"  @{account['handle']}: {s.get('followers_count')} followers")
        except Exception as e:
            lines.append(f"  @{account['handle']}: stats failed ({e})")
    return lines


def find_winners(rows: list[dict]) -> list[dict]:
    by_account = defaultdict(list)
    for r in rows:
        by_account[r["post"]["account_id"]].append(r["views"] or 0)
    known = {h["post_id"] for h in db.select("hooks", {"source": "eq.winner"}, columns="post_id")}
    # Keep winners' view counts current, so the weekly plan ranks patterns by today's numbers
    for r in rows:
        if r["post"]["id"] in known and r["views"]:
            db.update("hooks", {"post_id": f"eq.{r['post']['id']}"}, {"views": r["views"]})
    winners = []
    for r in rows:
        p, views = r["post"], r["views"] or 0
        if p["id"] in known or r["hours_live"] > WINNER_WINDOW_HOURS:
            continue
        account_views = by_account[p["account_id"]]
        relative = len(account_views) >= 10 and views >= 300 and views >= RELATIVE_WINNER * median(account_views)
        if views >= WINNER_VIEWS or relative:
            db.upsert("hooks", {"hook": p["hook"], "hook_type": p["hook_type"], "format": p["format"],
                                "topic": p["topic"], "source": "winner", "account_id": p["account_id"],
                                "post_id": p["id"], "views": views}, on_conflict="post_id")
            winners.append(r)
    return winners


def send_winner(r: dict) -> None:
    p = r["post"]
    telegram.send_message(f"🏆 Winner on @{HANDLES[p['account_id']]}: {r['views']} views in {r['hours_live']:.0f}h\n"
                          f"\"{p['hook']}\" ({p['format']}, {p['hook_type']})\n{p['permalink']}\n"
                          "Its hook pattern goes into next week's plan automatically.")


def daily_report(rows: list[dict]) -> str:
    since = (now() - timedelta(hours=24)).isoformat()
    published = db.select("posts", {"status": "eq.published", "published_at": f"gte.{since}"}, columns="account_id")
    failed = db.select("posts", {"status": "eq.failed", "scheduled_at": f"gte.{since}"}, columns="account_id,error")
    counts = defaultdict(int)
    for p in published:
        counts[p["account_id"]] += 1
    lines = [f"📊 Daily report: {len(published)} posts published, {len(failed)} failed in the last 24h"]
    lines += [f"  @{HANDLES[acc]}: {n}" for acc, n in sorted(counts.items())]
    if rows:
        top = sorted(rows, key=lambda r: r["views"] or 0, reverse=True)[:3]
        lines.append("Top posts this week (views):")
        lines += [f"  {r['views']} · @{HANDLES[r['post']['account_id']]} · {r['post']['hook'][:60]}" for r in top]
    return "\n".join(lines)


def refresh_tokens(cfg: dict) -> list[str]:
    problems = []
    stored = {r["account_id"]: r for r in db.select("ig_tokens")}
    for account in cfg["accounts"]:
        acc = account["id"]
        last = stored.get(acc)
        if last and datetime.fromisoformat(last["refreshed_at"]) > now() - timedelta(days=7):
            continue
        try:
            new = instagram.refresh_token(instagram.token(acc))
            db.upsert("ig_tokens", {"account_id": acc, "token": new["access_token"],
                                    "refreshed_at": now().isoformat()}, on_conflict="account_id")
        except Exception as e:
            problems.append(f"{acc}: {e}")
    return problems


def clean_media() -> None:
    before = (now() - timedelta(days=MEDIA_KEEP_DAYS)).isoformat()
    old = db.select("posts", {"published_at": f"lt.{before}", "media_keys": "not.is.null"}, columns="id,media_keys")
    for p in old:
        for key in p["media_keys"]:
            storage.delete(key)
        db.update("posts", {"id": f"eq.{p['id']}"}, {"media_keys": None})


def step(name: str, fn, problems: list[str], default=None):
    """Runs one nightly step; a failure is reported instead of stopping the other steps."""
    try:
        return fn()
    except Exception as e:
        print(f"step '{name}' failed: {e}")
        problems.append(f"{name}: {e}"[:300])
        return default


def main() -> None:
    cfg = load_accounts()
    problems: list[str] = []
    rows = step("metrics", collect_metrics, problems, default=[])
    for w in step("winners", lambda: find_winners(rows), problems, default=[]):
        step("send winner", lambda w=w: send_winner(w), problems)
    report = step("daily report", lambda: daily_report(rows), problems, default="📊 Daily report unavailable")
    followers = step("follower counts", lambda: collect_account_stats(cfg), problems, default=[])
    report += "\nFollowers:\n" + "\n".join(followers)
    token_problems = step("token refresh", lambda: refresh_tokens(cfg), problems, default=[])
    if token_problems:
        report += "\n⚠️ Token refresh failed:\n" + "\n".join(token_problems)
    step("media cleanup", clean_media, problems)
    if problems:
        report += "\n⚠️ Nightly steps with errors (others still ran):\n" + "\n".join(problems)
    print(report)
    telegram.send_message(report)
    if problems:
        raise SystemExit(1)  # keep the run marked failed in GitHub so it's visible


if __name__ == "__main__":
    main()
