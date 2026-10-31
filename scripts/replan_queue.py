"""One-off: drops queued (not yet rendered) posts matching a filter and refills their slots with the current
strategy (format mix, hooks, sources).

Run: python -m scripts.replan_queue --carousels [--dry-run]
     python -m scripts.replan_queue --refill-dropped   # finish an interrupted run
"""
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from engine import db, refill, telegram
from engine.config import load_accounts

KEEP_KINDS = {"news", "funding_roundup"}
MIN_LEAD_HOURS = 2
PENDING = "re-planned: Reels-first"
DONE = "re-planned: Reels-first, refilled"  # leave posts due very soon alone so their slots don't go empty while the batch runs


def main() -> None:
    cfg = load_accounts()
    after = (datetime.now(timezone.utc) + timedelta(hours=MIN_LEAD_HOURS)).isoformat()
    if "--refill-dropped" in sys.argv:
        # Slots dropped by an interrupted earlier run that were never refilled
        rows = db.select("posts", {"status": "eq.dropped", "error": f"eq.{PENDING}", "scheduled_at": f"gt.{after}"})
    else:
        rows = db.select("posts", {"status": "eq.planned", "scheduled_at": f"gt.{after}"})
    if "--carousels" in sys.argv:
        rows = [r for r in rows if r["format"] == "carousel" and r["kind"] not in KEEP_KINDS]
    print(f"{len(rows)} queued posts to re-plan")
    if "--dry-run" in sys.argv or not rows:
        return
    slots = defaultdict(list)
    for r in rows:
        # Dropped first so nothing publishes from the old plan; marked done only once the refill is submitted
        db.update("posts", {"id": f"eq.{r['id']}"}, {"status": "dropped", "error": PENDING})
        slots[r["account_id"]].append(datetime.fromisoformat(r["scheduled_at"]))
    counts = refill.submit(cfg, slots)
    for r in rows:
        db.update("posts", {"id": f"eq.{r['id']}"}, {"error": DONE})
    msg = (f"🔁 Re-planned {len(rows)} queued carousels as Reels-first with controversial hooks: "
           + ", ".join(f"{k} {v}" for k, v in counts.items()))
    print(msg)
    telegram.send_message(msg)


if __name__ == "__main__":
    main()
