"""One-off: drops queued posts built on invented characters and refills those slots from real sources.

Run: python -m scripts.replace_fiction [--dry-run]
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from engine import content, db, llm, planner, telegram
from engine.config import env, load_accounts

FICTION = re.compile(r"\b(imagine|hypothetical)\b", re.I)
CHARACTER_HOOK = re.compile(r"^(he|she|his|her|two founders)\b", re.I)


def is_fiction(row: dict) -> bool:
    return (row["hook_type"] == "story" or bool(CHARACTER_HOOK.search(row["hook"]))
            or bool(FICTION.search(json.dumps(row["content"]))))


def main() -> None:
    cfg = load_accounts()
    now = datetime.now(timezone.utc).isoformat()
    rows = db.select("posts", {"status": "in.(planned,ready)", "kind": "eq.evergreen", "scheduled_at": f"gt.{now}"})
    fiction = [r for r in rows if is_fiction(r)]
    print(f"{len(fiction)} of {len(rows)} queued posts use invented characters")
    if "--dry-run" in sys.argv or not fiction:
        return
    for r in fiction:
        db.update("posts", {"id": f"eq.{r['id']}"}, {"status": "dropped", "error": "replaced: invented story"})

    slots = defaultdict(list)
    for r in fiction:
        slots[r["account_id"]].append(datetime.fromisoformat(r["scheduled_at"]))
    start = min(min(v) for v in slots.values()).date()
    plan = planner.build_week(cfg, start, only_slots=slots)
    accounts = {a["id"]: a for a in cfg["accounts"]}
    model = llm.model_for(fast=False)
    avoid, proven = planner.recent_hooks(), planner.proven_hooks()

    def params(g: dict) -> dict:
        if g["kind"] == "evergreen":
            return content.request_params(model, accounts[g["account"]], g["topic"], len(g["angles"]),
                                          fmt=g["format"], avoid_hooks=avoid, proven_hooks=proven, angles=g["angles"])
        return content.sourced_params(model, accounts[g["account"]], g["format"], g["doc"])

    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    batch = client.messages.batches.create(requests=[
        Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**params(g))) for cid, g in plan.items()])
    db.insert("batches", {"provider_id": batch.id, "week_start": start.isoformat(), "plan": plan})
    kinds = defaultdict(int)
    for g in plan.values():
        kinds[g["kind"]] += len(g["slots"])
    msg = (f"🔁 Replaced {len(fiction)} queued posts that used invented characters. Refill being written: "
           + ", ".join(f"{k} {v}" for k, v in kinds.items()))
    print(msg)
    telegram.send_message(msg)


if __name__ == "__main__":
    main()
