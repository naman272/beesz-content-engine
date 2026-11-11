"""Own-product promos (config/promos.yaml): which promo is running and the source doc a promo post is written from."""
import itertools
from datetime import date

import yaml

from engine.config import ROOT


def load() -> list[dict]:
    return yaml.safe_load((ROOT / "config" / "promos.yaml").read_text())["promos"]


def active(day: date) -> dict | None:
    for p in load():
        if p["start"] <= day <= p["end"]:
            return p
    return None


def previous_hooks(limit: int = 30) -> list[str]:
    from engine import db
    rows = db.select("posts", {"kind": "eq.promo"}, columns="hook", order="created_at.desc", limit=limit)
    return [r["hook"] for r in rows]


def docs(promo: dict, count: int) -> list[dict]:
    """One doc per promo slot, each with its own angle so the week's promo posts don't repeat."""
    prev = previous_hooks()
    angles = itertools.cycle(promo["angles"])
    return [{"kind": "promo", "label": promo["name"], "promo": promo["id"], "url": promo["url"],
             "texts": [promo["brief"]], "angle": next(angles), "previous_hooks": prev}
            for _ in range(count)]
