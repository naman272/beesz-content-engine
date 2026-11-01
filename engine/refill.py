"""Re-plans specific posting slots (after dropping queued posts) and submits them as one AI batch."""
from collections import defaultdict
from datetime import datetime

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from engine import content, db, llm, planner
from engine.config import env


def submit(cfg: dict, slots: dict[str, list[datetime]]) -> dict[str, int]:
    """slots: account_id -> datetimes to fill. Returns posts planned per kind/format."""
    start = min(min(v) for v in slots.values()).date()
    plan = planner.build_week(cfg, start, only_slots=slots)
    accounts = {a["id"]: a for a in cfg["accounts"]}
    model = llm.model_for(fast=False)
    avoid, proven = planner.recent_hooks(), planner.proven_hooks()

    def params(g: dict) -> dict:
        return content.plan_entry_params(model, accounts[g["account"]], g, avoid, proven)

    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    batch = client.messages.batches.create(requests=[
        Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**params(g))) for cid, g in plan.items()])
    db.insert("batches", {"provider_id": batch.id, "week_start": start.isoformat(), "plan": plan})
    counts = defaultdict(int)
    for g in plan.values():
        counts[f"{g['kind']} {g['format']}"] += len(g["slots"])
    return dict(counts)
