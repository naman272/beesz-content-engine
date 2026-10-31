"""Turns a queued post into media files: picks concrete assets, renders, uploads to R2."""
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine import assets, db, storage
from engine.config import ROOT
from engine.render import animated, carousel, formats2d, reaction

WORK = ROOT / "output" / "render"


def recently_used(account_id: str, days: int = 14) -> set[str]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.select("posts", {"account_id": f"eq.{account_id}", "scheduled_at": f"gte.{since}",
                               "assets": "not.is.null"}, columns="assets")
    used = set()
    for r in rows:
        a = r["assets"]
        used.update(a.get("backgrounds", []))
        used.update(x for x in (a.get("music"), a.get("reaction")) if x)
    return used


def render(post_row: dict, account: dict) -> tuple[list[Path], dict]:
    """Returns (local files in publish order, assets used)."""
    post, fmt = post_row["content"], post_row["format"]
    out = WORK / post_row["id"]
    if out.exists():
        shutil.rmtree(out)
    avoid = recently_used(account["id"])
    style = account.get("background_style", "any")

    if fmt == "carousel":
        bg = assets.pick_background(post["background"], style, avoid)
        files = carousel.render(post, account, bg, out)
        return files, {"backgrounds": [bg["file"]]}

    if fmt == "reaction":
        clip = assets.pick_reaction(post["reaction"], avoid=avoid)
        backgrounds = []
        for point in post["points"]:
            bg = assets.pick_background(point["background"], style, avoid)
            avoid.add(bg["file"])
            backgrounds.append(bg)
        music = assets.pick_music(post["music_mood"], avoid)
        video = reaction.render(post, account, clip, backgrounds, assets.path(music["file"]), out / "reel.mp4")
        return [video], {"backgrounds": [b["file"] for b in backgrounds], "music": music["file"],
                         "music_credit": f"{music['title']} - {music['artist']}", "reaction": clip["file"]}

    if fmt == "animated" or fmt in formats2d.FORMATS:
        music = assets.pick_music(post["music_mood"], avoid)
        video = out / "reel.mp4"
        out.mkdir(parents=True, exist_ok=True)
        if fmt == "animated":
            animated.render(post, account, assets.path(music["file"]), video)
        else:
            formats2d.render(fmt, post, account, assets.path(music["file"]), video)
        shutil.rmtree(out / "hf_project", ignore_errors=True)
        return [video], {"music": music["file"], "music_credit": f"{music['title']} - {music['artist']}"}

    raise ValueError(f"no renderer for format {fmt}")


def upload(post_id: str, files: list[Path]) -> list[str]:
    keys = []
    for f in files:
        key = f"media/{post_id}/{f.name}"
        content_type = "video/mp4" if f.suffix == ".mp4" else "image/jpeg"
        storage.upload_file(key, str(f), content_type)
        keys.append(key)
    return keys
