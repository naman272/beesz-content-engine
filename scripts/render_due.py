"""Renders posts scheduled in the next few hours and uploads them to R2 (status planned -> ready).

Run: python -m scripts.render_due [--hours 8]
"""
import shutil
import sys
from datetime import datetime, timedelta, timezone

from engine import db, produce, telegram
from engine.config import load_accounts


def main() -> None:
    hours = float(sys.argv[sys.argv.index("--hours") + 1]) if "--hours" in sys.argv else 8
    until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    accounts = {a["id"]: a for a in load_accounts()["accounts"]}
    due = db.select("posts", {"status": "eq.planned", "scheduled_at": f"lte.{until}"}, order="scheduled_at.asc")
    failures = []
    for row in due:
        try:
            files, used = produce.render(row, accounts[row["account_id"]])
            keys = produce.upload(row["id"], files)
            db.update("posts", {"id": f"eq.{row['id']}"}, {"status": "ready", "assets": used, "media_keys": keys})
            shutil.rmtree(produce.WORK / row["id"], ignore_errors=True)
            print(f"ready: {row['account_id']} {row['format']} {row['hook']!r}")
        except Exception as e:
            db.update("posts", {"id": f"eq.{row['id']}"}, {"status": "failed", "error": f"render: {e}"[:1000]})
            failures.append(f"{row['account_id']} {row['format']}: {e}")
            print(f"FAILED: {row['id']}: {e}")
    if failures:
        telegram.send_message("⚠️ Render failures:\n" + "\n".join(failures)[:3500])
    print(f"rendered {len(due) - len(failures)}/{len(due)}")


if __name__ == "__main__":
    main()
