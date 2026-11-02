"""Plans next week (Sunday to Saturday) once a week, right after the Sunday review, and submits it to the
Anthropic Batch API (50% cheaper). Results are picked up by scripts.collect_batches.

Run: python -m scripts.plan_week               # plans the week starting this/next Sunday, if not planned yet
     python -m scripts.plan_week --force       # plan even if that week is already planned
"""
import json
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from engine import content, db, llm, planner, telegram
from engine.config import ROOT, env, load_accounts


def week_start(cfg: dict) -> date:
    """Weeks run Sunday to Saturday. On Sunday that's today; otherwise the coming Sunday."""
    today = datetime.now(ZoneInfo(cfg["timezone"])).date()
    return max(cfg["launch_date"], today + timedelta(days=(6 - today.weekday()) % 7))


def load_learnings() -> list[str]:
    """What last week's review found (written by scripts.weekly_review just before planning)."""
    path = ROOT / "output" / "weekly_insights.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return ([f"Working: {w}" for w in data.get("working", [])] + [f"Not working: {w}" for w in data.get("not_working", [])]
            + [f"Try: {x['title']} ({x['why']})" for x in data.get("suggestions", [])[:3]])


def main() -> None:
    cfg = load_accounts()
    force = "--force" in sys.argv
    if db.select("batches", {"status": "eq.submitted"}, columns="id") and not force:
        print("A batch is still being written; skipping.")
        return
    start = week_start(cfg)
    if db.select("batches", {"week_start": f"eq.{start.isoformat()}"}, columns="id") and not force:
        print(f"Week of {start} is already planned; skipping.")
        return
    content.LEARNINGS = load_learnings()

    plan = planner.build_week(cfg, start)
    accounts = {a["id"]: a for a in cfg["accounts"]}
    avoid, proven = planner.recent_hooks(), planner.proven_hooks()
    model = llm.model_for(fast=False)
    def params(g: dict) -> dict:
        return content.plan_entry_params(model, accounts[g["account"]], g, avoid, proven)

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
