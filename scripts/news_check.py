"""Hourly: turns the most important new startup stories into posts (on top of the daily quota).

Run: python -m scripts.news_check            # queue posts
     python -m scripts.news_check --dry-run  # score and print only
"""
import os
import random
import sys
from collections import Counter
from datetime import datetime, time
from zoneinfo import ZoneInfo

from engine import checks, db, news, telegram
from engine.config import load_accounts

MAX_SCORED_PER_RUN = 60


def todays_news(tz: ZoneInfo) -> Counter:
    start = datetime.combine(datetime.now(tz).date(), time(0), tz).isoformat()
    rows = db.select("posts", {"kind": "eq.news", "created_at": f"gte.{start}"}, columns="account_id")
    return Counter(r["account_id"] for r in rows)


def pick_account(preferred: str, used: Counter, cfg: dict, accounts: dict) -> str | None:
    cap = cfg["max_per_account_per_day"]
    if used[preferred] < cap:
        return preferred
    free = [a for a in accounts if used[a] < cap]
    return min(free, key=lambda a: used[a]) if free else None


def pick_format(account: dict, item: dict, ready: list[str]) -> str:
    """News follows the account's format mix (Reels-first), so it doesn't skew the share of carousels."""
    from datetime import date
    from engine.config import load_accounts
    from engine.planner import KIND_FORMATS, mix_for
    today = mix_for(load_accounts(), account, date.today())
    mix = {f: w for f, w in today.items() if f in ready and f in KIND_FORMATS["news"]} or {"carousel": 1}
    return random.choices(list(mix), weights=list(mix.values()))[0]


def main() -> None:
    dry = "--dry-run" in sys.argv
    cfg, acc_cfg = news.settings(), load_accounts()
    accounts = {a["id"]: a for a in acc_cfg["accounts"]}
    tz = ZoneInfo(acc_cfg["timezone"])

    items = sorted(news.fetch_new(cfg, skip_seen=not dry), key=lambda i: i["published_at"], reverse=True)[:MAX_SCORED_PER_RUN]
    print(f"{len(items)} new stories")
    if not items:
        return _output(0)
    items = news.score(cfg, items, acc_cfg["accounts"])

    for it in sorted(items, key=lambda i: i.get("score", 0), reverse=True)[:15]:
        print(f"  {it.get('score', '?'):>2} {it['source']}: {it['title'][:80]} -> {it.get('reason', '')[:80]}")
    if dry:
        return

    db.upsert("news_items", [{k: it.get(k) for k in ("url", "source", "title", "published_at", "score",
                                                     "takeaway", "reason")} for it in items], on_conflict="url")

    used = todays_news(tz)
    created = 0
    candidates = [i for i in items if i.get("score", 0) >= cfg["min_score"] and i.get("takeaway")]
    for item in sorted(candidates, key=lambda i: i["score"], reverse=True):
        if sum(used.values()) >= cfg["max_per_day"]:
            break
        account_id = pick_account(item.get("account"), used, cfg, accounts)
        if not account_id:
            break
        article = news.article_text(item["url"])
        if len(article) < cfg["min_article_chars"]:
            db.update("news_items", {"url": f"eq.{item['url']}"}, {"reason": "skipped: article text unavailable"})
            continue
        account = accounts[account_id]
        fmt = pick_format(account, item, acc_cfg["ready_formats"])
        source = item["title"] + "\n" + article
        post, problems = None, ["not written"]
        for _ in range(2):  # one retry if the checks fail
            post = news.write_post(account, fmt, item, article)
            problems = checks.check_post(post, fmt, source_text=source) if post else ["empty output"]
            if not problems:
                break
        if problems:
            print(f"  dropped {item['title'][:60]}: {problems}")
            db.update("news_items", {"url": f"eq.{item['url']}"}, {"reason": f"dropped: {problems}"[:500]})
            continue

        post.update(kicker="NEWS", source_name=item["source"])
        # Stock photos of people next to a real story could be mistaken for the people in it
        swap = {"office": "abstract-texture"}
        if "background" in post:
            post["background"] = swap.get(post["background"], post["background"])
        for point in post.get("points", []):
            point["background"] = swap.get(point["background"], point["background"])
        row = db.insert("posts", {
            "account_id": account_id, "format": fmt, "topic": post["topic"], "hook_type": post["hook_type"],
            "hook": post["hook"], "content": post, "status": "planned", "kind": "news",
            "source_url": item["url"], "scheduled_at": news.publish_time(cfg, tz).isoformat(),
        })[0]
        db.update("news_items", {"url": f"eq.{item['url']}"}, {"post_id": row["id"], "account_id": account_id})
        used[account_id] += 1
        created += 1
        telegram.send_message(f"📰 News post queued for @{account['handle']} ({fmt}, score {item['score']}/10)\n"
                              f"\"{post['hook']}\"\nWhy: {item['takeaway']}\n{item['url']}")
        print(f"  queued for {account_id}: {post['hook']}")
    _output(created)


def _output(created: int) -> None:
    """Tells the workflow whether to install render tools and publish now."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"created={created}\n")
    print(f"news posts queued: {created}")


if __name__ == "__main__":
    main()
