"""How well each reaction clip holds viewers (median skip rate of the Reels that used it), so renders can favour
the faces that keep people watching. Recomputed from live metrics once per process."""
import statistics
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from engine import db

MIN_VIEWS = 20      # skip rate on near-zero-view posts is noise
MIN_REELS = 5       # clips with fewer data points get the average weight
LOOKBACK_DAYS = 45


@lru_cache(maxsize=1)
def skip_by_clip() -> dict[str, float]:
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    posts = db.select("posts", {"format": "eq.reaction", "status": "eq.published", "published_at": f"gte.{since}"},
                      columns="id,assets", limit=2000)
    clip_of = {p["id"]: (p.get("assets") or {}).get("reaction") for p in posts}
    ids = [i for i, c in clip_of.items() if c]
    latest = {}
    for i in range(0, len(ids), 150):
        for m in db.select("metrics", {"post_id": f"in.({','.join(ids[i:i + 150])})", "skip_rate": "not.is.null"},
                           columns="post_id,skip_rate,views,captured_at", order="captured_at.asc"):
            latest[m["post_id"]] = m
    by_clip: dict[str, list[float]] = {}
    for pid, m in latest.items():
        if (m["views"] or 0) >= MIN_VIEWS:
            by_clip.setdefault(clip_of[pid], []).append(float(m["skip_rate"]))
    return {c: statistics.median(v) for c, v in by_clip.items() if len(v) >= MIN_REELS}


def weights(files: list[str]) -> list[float]:
    """Higher for clips people skip less: (60 - median skip)^2, so a 44% clip gets ~4x a 52% one and ~16x a 56% one."""
    try:
        skips = skip_by_clip()
    except Exception as e:  # metrics unavailable: pick evenly rather than fail the render
        print(f"clip stats unavailable ({type(e).__name__}); picking evenly")
        return [1.0] * len(files)
    default = statistics.median(skips.values()) if skips else 50.0
    return [max(1.0, 60 - skips.get(f, default)) ** 2 for f in files]
