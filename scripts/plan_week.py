"""Plans the next 7 days of posts and submits them to the Anthropic Batch API (50% cheaper).
Results are picked up by scripts.collect_batches.

Run: python -m scripts.plan_week               # plans the 7 days after the last scheduled post
     python -m scripts.plan_week --force       # plan even if a week is already queued
"""
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from engine import content, db, llm, planner, telegram
from engine.config import env, load_accounts


def next_start(cfg: dict) -> date:
    tz = ZoneInfo(cfg["timezone"])
    tomorrow = datetime.now(tz).date() + timedelta(days=1)
    last = db.select("posts", {"status": "neq.dropped"}, columns="scheduled_at", order="scheduled_at.desc", limit=1)
    after_last = (datetime.fromisoformat(last[0]["scheduled_at"]).astimezone(tz).date() + timedelta(days=1)
                  if last else tomorrow)
    return max(cfg["launch_date"], tomorrow, after_last)


def main() -> None:
    cfg = load_accounts()
    force = "--force" in sys.argv
    if db.select("batches", {"status": "eq.submitted"}, columns="id") and not force:
        print("A batch is still being written; skipping.")
        return
    start = next_start(cfg)
    today = datetime.now(ZoneInfo(cfg["timezone"])).date()
    if (start - today).days > 3 and not force:
        print(f"Already planned until {start - timedelta(days=1)}; skipping.")
        return

    plan = planner.build_week(cfg, start)
    accounts = {a["id"]: a for a in cfg["accounts"]}
    avoid, proven = planner.recent_hooks(), planner.proven_hooks()
    model = llm.model_for(fast=False)
    def params(g: dict) -> dict:
        if g.get("kind", "evergreen") == "evergreen":
            return content.request_params(model, accounts[g["account"]], g["topic"], len(g["angles"]),
                                          fmt=g["format"], avoid_hooks=avoid, proven_hooks=proven,
                                          angles=g["angles"])
        return content.sourced_params(model, accounts[g["account"]], g["format"], g["doc"])

    requests = [Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**params(g)))
                for cid, g in plan.items()]
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    batch = client.messages.batches.create(requests=requests)
    db.insert("batches", {"provider_id": batch.id, "week_start": start.isoformat(), "plan": plan})

    total = sum(len(g["slots"]) for g in plan.values())
    msg = (f"🗓 Planning {start:%a %d %b} – {start + timedelta(days=6):%a %d %b}: {total} posts "
           f"across {len(accounts)} accounts ({len(requests)} AI requests). I'll report when they're written.")
    print(msg)
    telegram.send_message(msg)


if __name__ == "__main__":
    main()
