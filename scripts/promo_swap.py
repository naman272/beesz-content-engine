"""One-off: swaps already-queued posts for promo Reels of the active promo (config/promos.yaml), N per account
per day, for promos that start mid-week. From the next Sunday plan on, promos get their share automatically.

Picks the weakest formats first and never touches news, funding roundups or posts due within MIN_LEAD_HOURS.

Run: python -m scripts.promo_swap [--per-day 1] [--dry-run]
"""
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from engine import db, promos, refill, telegram
from engine.config import load_accounts

MIN_LEAD_HOURS = 12  # leave time for the batch to be written and the post rendered
KEEP_KINDS = {"news", "funding_roundup", "promo"}
# Swap these first (weakest by views since 4 Nov), reaction Reels last
FORMAT_ORDER = ["carousel", "checklist", "animated", "chat", "explainer", "myth_fact", "reaction"]
PENDING = "swapped for promo"
DONE = "swapped for promo, refilled"


def main() -> None:
    cfg = load_accounts()
    tz = ZoneInfo(cfg["timezone"])
    per_day = int(sys.argv[sys.argv.index("--per-day") + 1]) if "--per-day" in sys.argv else 1
    now = datetime.now(timezone.utc)
    promo = promos.active((now + timedelta(hours=MIN_LEAD_HOURS)).astimezone(tz).date())
    if not promo:
        print("No promo is active.")
        return
    after = (now + timedelta(hours=MIN_LEAD_HOURS)).isoformat()
    rows = db.select("posts", {"status": "eq.planned", "scheduled_at": f"gt.{after}"}, order="scheduled_at.asc")
    by_day = defaultdict(list)
    for r in rows:
        if r["kind"] in KEEP_KINDS:
            continue
        day = datetime.fromisoformat(r["scheduled_at"]).astimezone(tz).date()
        if day <= promo["end"]:
            by_day[(r["account_id"], day)].append(r)
    picked = []
    for (_, _), posts in sorted(by_day.items()):
        posts.sort(key=lambda r: FORMAT_ORDER.index(r["format"]) if r["format"] in FORMAT_ORDER else 0)
        picked += posts[:per_day]

    for r in picked:
        print(f"{r['account_id']} {r['scheduled_at']} {r['format']:10} {r['kind']:10} {r['hook']}")
    print(f"{len(picked)} queued posts to swap for {promo['name']} promos")
    if "--dry-run" in sys.argv or not picked:
        return
    slots = defaultdict(list)
    for r in picked:  # dropped first so nothing publishes from the old plan
        db.update("posts", {"id": f"eq.{r['id']}"}, {"status": "dropped", "error": PENDING})
        slots[r["account_id"]].append(datetime.fromisoformat(r["scheduled_at"]))
    counts = refill.submit(cfg, slots, force_kind="promo")
    for r in picked:
        db.update("posts", {"id": f"eq.{r['id']}"}, {"error": DONE})
    msg = (f"📣 Swapped {len(picked)} queued posts for {promo['name']} promo Reels "
           f"({per_day}/account/day): " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    print(msg)
    telegram.send_message(msg)


if __name__ == "__main__":
    main()
