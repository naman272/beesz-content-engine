"""Picks concrete asset files from the categories the AI chose."""
import json
import random
from pathlib import Path

import yaml

from engine.config import ROOT

# Licensed media (stock images, music, purchased reaction clips) lives in a separate private repo at media/
LIB = ROOT / "media" / "library"


def _index() -> dict:
    return json.loads((LIB / "index.json").read_text())


def _bg_config() -> dict:
    return yaml.safe_load((ROOT / "config" / "backgrounds.yaml").read_text())


def backgrounds() -> dict[str, list[dict]]:
    """category -> [{file, brightness, style}] with excluded files removed."""
    cfg = _bg_config()
    excluded, illustrations = set(cfg["exclude"]), set(cfg["illustration"])
    out = {}
    for cat, entries in _index()["backgrounds"].items():
        items = []
        for e in entries:
            name = Path(e["file"]).name
            if name in excluded:
                continue
            items.append({**e, "style": "illustration" if name in illustrations else "photo"})
        out[cat] = items
    return out


def background_categories() -> list[str]:
    return sorted(backgrounds())


def music_moods() -> list[str]:
    return sorted(_index()["music"])


def pick_background(category: str, style: str = "any", avoid: set[str] = frozenset()) -> dict:
    pool = backgrounds().get(category) or [e for v in backgrounds().values() for e in v]
    if style != "any":
        pool = [e for e in pool if e["style"] == style] or pool
    fresh = [e for e in pool if e["file"] not in avoid] or pool
    return random.choice(fresh)


def pick_music(mood: str, avoid: set[str] = frozenset()) -> dict:
    music = _index()["music"]
    pool = music.get(mood) or [e for v in music.values() for e in v]
    fresh = [e for e in pool if e["file"] not in avoid] or pool
    return random.choice(fresh)


REACTIONS = ROOT / "media" / "reactions"


def _reactions() -> list[dict]:
    return yaml.safe_load((REACTIONS / "index.yaml").read_text())["clips"]


def reaction_emotions() -> list[str]:
    return sorted({c["emotion"] for c in _reactions()})


def pick_reaction(emotion: str, creator: str | None = None, avoid: set[str] = frozenset()) -> dict:
    clips = _reactions()
    pool = [c for c in clips if c["emotion"] == emotion] or clips
    if creator:
        pool = [c for c in pool if c["creator"] == creator] or pool
    fresh = [c for c in pool if c["file"] not in avoid] or pool
    return random.choice(fresh)


def reaction_path(clip: dict) -> Path:
    return REACTIONS / clip["file"]


def path(rel: str) -> Path:
    return LIB / rel
