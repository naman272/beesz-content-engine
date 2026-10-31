"""Publishes ready posts whose time has come (status ready -> published).

Run: python -m scripts.publish_due
"""
from datetime import datetime, timedelta, timezone

from engine import db, instagram, storage, telegram

STALE_HOURS = 12  # don't publish posts that are more than this late (avoids bursts after an outage)
USAGE_PAUSE = 75  # stop publishing this run once Meta reports this % of the hourly allowance used


def caption(post: dict) -> str:
    return post["caption"] + "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in post["hashtags"])


def main() -> None:
    now = datetime.now(timezone.utc)
    due = db.select("posts", {"status": "eq.ready", "scheduled_at": f"lte.{now.isoformat()}"},
                    order="scheduled_at.asc")
    failures, paused, published = [], None, 0
    for row in due:
        if instagram.usage["pct"] >= USAGE_PAUSE:
            paused = f"Meta usage at {instagram.usage['pct']}% of the hourly allowance"
            break
        if datetime.fromisoformat(row["scheduled_at"]) < now - timedelta(hours=STALE_HOURS):
            db.update("posts", {"id": f"eq.{row['id']}"}, {"status": "failed", "error": "missed its slot"})
            continue
        urls = [storage.public_url(k) for k in row["media_keys"]]
        try:
            # A retried post may already be live (e.g. throttled after publishing); never post it twice
            if row.get("error"):
                live = instagram.find_live(row["account_id"], caption(row["content"]))
                if live:
                    db.update("posts", {"id": f"eq.{row['id']}"}, {
                        "status": "published", "ig_media_id": live["id"], "permalink": live["permalink"],
                        "published_at": live["timestamp"], "error": None})
                    print(f"already live, recorded: {row['account_id']} {live['permalink']}")
                    published += 1
                    continue
            if row["format"] == "carousel":
                result = instagram.publish_carousel(row["account_id"], urls, caption(row["content"]))
            else:
                result = instagram.publish_reel(row["account_id"], urls[0], caption(row["content"]))
            db.update("posts", {"id": f"eq.{row['id']}"}, {
                "status": "published", "ig_media_id": result["id"], "permalink": result["permalink"],
                "published_at": datetime.now(timezone.utc).isoformat(),
            })
            print(f"published: {row['account_id']} {row['format']} {result['permalink']}")
            published += 1
            if row.get("kind") == "news":
                telegram.send_message(f"📰 News post live: \"{row['hook']}\"\n{result['permalink']}")
        except instagram.RateLimited as e:
            # Leave it queued; the next hourly run retries it
            db.update("posts", {"id": f"eq.{row['id']}"}, {"error": f"retrying: {e}"[:1000]})
            paused = str(e)
            break
        except Exception as e:
            db.update("posts", {"id": f"eq.{row['id']}"}, {"status": "failed", "error": f"publish: {e}"[:1000]})
            failures.append(f"{row['account_id']} {row['format']} {row['hook']!r}: {e}")
            print(f"FAILED: {row['id']}: {e}")
    if failures:
        telegram.send_message("⚠️ Publish failures:\n" + "\n".join(failures)[:3500])
    if paused:
        print(f"paused for this hour: {paused}. Remaining posts stay queued for the next run.")
    print(f"published {published}/{len(due)}")


if __name__ == "__main__":
    main()
