"""Instagram API with Instagram Login (graph.instagram.com): publishing, insights, tokens."""
import json
import re
import time
from functools import cache

import requests

from engine import db
from engine.config import ig_token

BASE = "https://graph.instagram.com/v25.0"
# "reposts" is documented but rejected by the API for our media, and it breaks the whole request
COMMON = ["views", "reach", "likes", "comments", "saved", "shares", "total_interactions"]
METRICS = {
    "carousel": COMMON + ["profile_visits", "profile_activity", "follows"],
    "reaction": COMMON + ["ig_reels_avg_watch_time", "ig_reels_video_view_total_time", "reels_skip_rate"],
}


class RateLimited(RuntimeError):
    """Meta throttled us (app or account limit) or asked us to retry later. Safe to retry next run."""


RATE_LIMIT_CODES = {4, 17, 32, 613, 80002}
TRANSIENT_CODES = {1, 2}
usage = {"pct": 0}  # highest % of Meta's hourly allowance seen in this run


def _call(method: str, url: str, params: dict) -> dict:
    r = requests.request(method, url, params=params, timeout=60)
    header = r.headers.get("x-app-usage") or r.headers.get("x-business-use-case-usage")
    if header:
        try:
            parsed = json.loads(header)
            values = [v for k, v in parsed.items() if isinstance(v, (int, float))] if isinstance(parsed, dict) else []
            usage["pct"] = max([usage["pct"], *values])
        except ValueError:
            pass
    data = r.json()
    if r.status_code != 200 or "error" in data:
        err = data.get("error", {})
        msg = err.get("message", r.text)
        if err.get("code") in RATE_LIMIT_CODES or err.get("code") in TRANSIENT_CODES or "limit" in msg.lower():
            raise RateLimited(f"Instagram API error: {msg}")
        raise RuntimeError(f"Instagram API error: {msg}")
    return data


def me(token: str) -> dict:
    return _call("GET", f"{BASE}/me", {"fields": "user_id,username,account_type", "access_token": token})


def refresh_token(token: str) -> dict:
    """Extends a long-lived token by 60 days. Token must be at least 24h old and not expired."""
    return _call("GET", "https://graph.instagram.com/refresh_access_token",
                 {"grant_type": "ig_refresh_token", "access_token": token})


_tokens: dict[str, str] = {}


def token(account_id: str) -> str:
    """Latest refreshed token from the database (looked up once per run), falling back to .env / secrets."""
    if account_id not in _tokens:
        rows = db.select("ig_tokens", {"account_id": f"eq.{account_id}"}, columns="token")
        _tokens[account_id] = rows[0]["token"] if rows else ig_token(account_id)
    return _tokens[account_id]


@cache
def user_id(account_id: str) -> str:
    return me(token(account_id))["user_id"]


def _container(account_id: str, params: dict) -> str:
    params = {**params, "access_token": token(account_id)}
    return _call("POST", f"{BASE}/{user_id(account_id)}/media", params)["id"]


def _wait(account_id: str, container_id: str, timeout: int, first_check: int, every: int) -> None:
    """Polls a container sparingly: each status check counts against Meta's hourly allowance."""
    time.sleep(first_check)
    deadline = time.time() + timeout
    while True:
        status = _call("GET", f"{BASE}/{container_id}",
                       {"fields": "status_code,status", "access_token": token(account_id)})
        code = status.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram media processing failed: {status.get('status')}")
        if time.time() > deadline:
            raise RuntimeError("Instagram media processing timed out")
        time.sleep(every)


def _publish(account_id: str, container_id: str) -> dict:
    media_id = _call("POST", f"{BASE}/{user_id(account_id)}/media_publish",
                     {"creation_id": container_id, "access_token": token(account_id)})["id"]
    # The post is live now. The link is nice to have, so a failure here must never undo that.
    try:
        info = _call("GET", f"{BASE}/{media_id}", {"fields": "permalink", "access_token": token(account_id)})
        permalink = info.get("permalink")
    except RuntimeError:
        permalink = None
    return {"id": media_id, "permalink": permalink}


def find_live(account_id: str, caption: str, limit: int = 15) -> dict | None:
    """A recent post on the account with this caption, if a previous attempt already published it."""
    data = _call("GET", f"{BASE}/{user_id(account_id)}/media",
                 {"fields": "id,caption,permalink,timestamp", "limit": limit, "access_token": token(account_id)})
    start = caption.strip()[:80]
    for m in data.get("data", []):
        if (m.get("caption") or "").strip()[:80] == start:
            return {"id": m["id"], "permalink": m.get("permalink"),
                    "timestamp": m["timestamp"].replace("+0000", "+00:00")}
    return None


def publish_carousel(account_id: str, image_urls: list[str], caption: str) -> dict:
    children = [_container(account_id, {"image_url": url, "is_carousel_item": "true"}) for url in image_urls[:10]]
    # Images process in seconds; check only the last slide instead of polling every one
    _wait(account_id, children[-1], timeout=120, first_check=5, every=10)
    container = _container(account_id, {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption})
    _wait(account_id, container, timeout=120, first_check=5, every=10)
    return _publish(account_id, container)


def publish_reel(account_id: str, video_url: str, caption: str) -> dict:
    container = _container(account_id, {"media_type": "REELS", "video_url": video_url, "caption": caption,
                                        "share_to_feed": "true"})
    _wait(account_id, container, timeout=600, first_check=30, every=20)
    return _publish(account_id, container)


def account_stats(account_id: str) -> dict:
    return _call("GET", f"{BASE}/me", {"fields": "followers_count,follows_count,media_count",
                                       "access_token": token(account_id)})


_unsupported: set[str] = set()


def insights(account_id: str, media_id: str, fmt: str) -> dict:
    """Returns {metric: value} plus "profile_activity_breakdown"; unsupported metrics are skipped."""
    def fetch(metrics: list[str], **extra) -> list[dict]:
        return _call("GET", f"{BASE}/{media_id}/insights",
                     {"metric": ",".join(metrics), "access_token": token(account_id), **extra}).get("data", [])

    metrics = [m for m in (METRICS["carousel"] if fmt == "carousel" else METRICS["reaction"])  # other formats are Reels
               if m not in _unsupported]
    try:
        data = fetch(metrics)
    except RateLimited:
        raise
    except RuntimeError as e:
        # Instagram names the metrics it rejects; drop them for the rest of this run and retry once
        rejected = re.search(r"does not support the metrics?: ([\w, ]+)", str(e))
        if not rejected:
            raise
        _unsupported.update(m.strip() for m in rejected.group(1).split(","))
        data = fetch([m for m in metrics if m not in _unsupported])
    out = {m["name"]: (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
           for m in data}

    if "profile_activity" in metrics:
        try:
            rows = fetch(["profile_activity"], breakdown="action_type")
            results = rows[0].get("total_value", {}).get("breakdowns", [{}])[0].get("results", []) if rows else []
            out["profile_activity_breakdown"] = {r["dimension_values"][0]: r["value"] for r in results}
        except RateLimited:
            raise
        except (RuntimeError, IndexError, KeyError):
            pass
    return out
