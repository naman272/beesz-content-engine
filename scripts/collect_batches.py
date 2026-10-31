"""Collects finished AI batches: checks every post, rewrites failures once, queues the rest.

Run: python -m scripts.collect_batches   (safe to run often; does nothing while batches are in progress)
"""
from datetime import datetime, timezone

import anthropic

from engine import checks, content, db, llm, planner, telegram
from engine.config import env, load_accounts


def rewrite(client, model, account, group, i, problems, avoid) -> dict | None:
    notes = "; ".join(problems)
    if group.get("kind", "evergreen") == "evergreen":
        params = content.request_params(model, account, group["topic"], 1, fmt=group["format"],
                                        avoid_hooks=avoid, angles=[group["angles"][i]], fix_notes=notes)
    else:
        params = content.sourced_params(model, account, group["format"], group["doc"], fix_notes=notes)
    with client.messages.stream(**params) as stream:
        message = stream.get_final_message()
    posts = content.parse_posts(message)
    return posts[0] if posts else None


def check(post: dict, group: dict, avoid: list[str]) -> list[str]:
    doc = group.get("doc")
    if not doc:
        return checks.check_post(post, group["format"], avoid)
    problems = checks.check_post(post, group["format"], avoid, source_texts=doc["texts"])
    if doc["kind"] == "india_admin" and post.get("slides"):
        if len(post["slides"]) > 5:
            problems.append(f"India guide too long: {len(post['slides'])} slides (max 5)")
        long = [i for i, s in enumerate(post["slides"], 1) if len(s["body"]) > 160]
        if long:
            problems.append(f"India guide slide bodies over 140 chars: {long}")
    return problems


def collect(client, row: dict, cfg: dict) -> str:
    batch = client.messages.batches.retrieve(row["provider_id"])
    if batch.processing_status != "ended":
        return ""
    accounts = {a["id"]: a for a in cfg["accounts"]}
    model = llm.model_for(fast=False)
    avoid = planner.recent_hooks()
    plan = row["plan"]
    queued = rewritten = dropped = errored = 0
    cost = 0.0
    rows = []

    for result in client.messages.batches.results(row["provider_id"]):
        group = plan[result.custom_id]
        if result.result.type != "succeeded":
            errored += len(group["slots"])
            continue
        message = result.result.message
        cost += llm.cost_usd(model, message.usage, batch=True)
        posts = content.parse_posts(message)
        account = accounts[group["account"]]
        for i, slot in enumerate(group["slots"]):
            post = posts[i] if i < len(posts) else None
            problems = check(post, group, avoid) if post else ["missing from AI output"]
            if problems:
                post = rewrite(client, model, account, group, i, problems, avoid)
                rewritten += 1
                problems = check(post, group, avoid) if post else ["rewrite failed"]
            if problems:
                dropped += 1
                print(f"dropped {result.custom_id}#{i}: {problems}")
                continue
            avoid.append(post["hook"])
            doc = group.get("doc") or {}
            if doc.get("kind") == "breakdown":
                post["source_name"] = doc.get("source_name")
            rows.append({
                "kind": group.get("kind", "evergreen"), "source_url": doc.get("source_url"),
                "account_id": group["account"], "format": group["format"], "topic": post["topic"],
                "hook_type": post["hook_type"], "hook": post["hook"], "content": post,
                "status": "planned", "scheduled_at": slot, "batch_id": row["id"],
            })
            queued += 1

    for start in range(0, len(rows), 200):
        db.insert("posts", rows[start:start + 200])
    db.update("batches", {"id": f"eq.{row['id']}"}, {
        "status": "collected", "collected_at": datetime.now(timezone.utc).isoformat(),
        "usage": {"cost_usd": round(cost, 3), "queued": queued, "rewritten": rewritten,
                  "dropped": dropped, "errored": errored},
    })
    return (f"✍️ Week of {row['week_start']} written: {queued} posts queued, {rewritten} rewritten after checks, "
            f"{dropped} dropped, {errored} failed. Writing cost ≈ ${cost:.2f} (+ rewrites).")


def main() -> None:
    cfg = load_accounts()
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    for row in db.select("batches", {"status": "eq.submitted"}):
        report = collect(client, row, cfg)
        if report:
            print(report)
            telegram.send_message(report)
        else:
            print(f"batch {row['provider_id']} still processing")


if __name__ == "__main__":
    main()
