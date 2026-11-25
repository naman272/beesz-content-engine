"""Winner remixes: a Reel that took off is re-made the next week on 2 other accounts (fresh hook and wording,
different face clip, same facts), so one hit gets three shots. Remixes take slots from the winner share."""
import random
from collections import Counter
from datetime import datetime, timedelta, timezone

from engine import db

PER_WINNER = 2
LOOKBACK_DAYS = 14


def _text(post: dict) -> str:
    from engine.checks import _all_text
    return _all_text(post)


def candidates() -> list[dict]:
    """Recent winners (our own posts) not remixed yet, biggest first. Remixes are never remixed again."""
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    hooks = db.select("hooks", {"source": "eq.winner", "active": "is.true", "created_at": f"gte.{since}",
                                "post_id": "not.is.null"}, columns="post_id,views", order="views.desc.nullslast")
    docs = []
    for h in hooks:
        pid = h["post_id"]
        if db.select("posts", {"source_url": f"eq.remix:{pid}"}, columns="id", limit=1):
            continue
        rows = db.select("posts", {"id": f"eq.{pid}"}, columns="id,account_id,kind,content,assets", limit=1)
        if not rows or rows[0]["kind"] == "remix" or not rows[0].get("content"):
            continue
        post = rows[0]
        docs.append({"kind": "remix", "label": post["content"]["hook"], "views": h.get("views") or "",
                     "source_url": f"remix:{pid}", "urls": [], "texts": [_text(post["content"])],
                     "from_account": post["account_id"],
                     "avoid_reaction": (post.get("assets") or {}).get("reaction")})
    return docs


def assign(account_ids: list[str], docs: list[dict]) -> dict[str, list[dict]]:
    """Each winner goes to PER_WINNER other accounts, spreading the load evenly."""
    load, out = Counter(), {a: [] for a in account_ids}
    for d in docs:
        others = [a for a in account_ids if a != d["from_account"]]
        random.shuffle(others)
        for a in sorted(others, key=lambda a: load[a])[:PER_WINNER]:
            out[a].append(d)
            load[a] += 1
    return out
