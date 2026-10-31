"""Breaking news: fetch feeds -> filter with a cheap model -> write a grounded post with the main model."""
import json
from datetime import datetime, time, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import anthropic
import feedparser
import requests
import trafilatura
import yaml

from engine import content, db, llm
from engine.config import ROOT, env

UA = {"User-Agent": "Mozilla/5.0 (compatible; BeeszNewsBot/1.0)"}
UTC = ZoneInfo("UTC")


def settings() -> dict:
    return yaml.safe_load((ROOT / "config" / "news.yaml").read_text())


def _published(entry) -> datetime | None:
    for key in ("published", "updated"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            try:
                dt = datetime.fromisoformat(raw)
            except ValueError:
                continue
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return None


def fetch_new(cfg: dict, skip_seen: bool = True) -> list[dict]:
    """Recent stories across all feeds that we haven't scored before."""
    cutoff = datetime.now(UTC) - timedelta(hours=cfg["max_age_hours"])
    items = {}
    for feed in cfg["feeds"]:
        try:
            parsed = feedparser.parse(requests.get(feed["url"], headers=UA, timeout=30).content)
        except requests.RequestException as e:
            print(f"feed failed {feed['name']}: {e}")
            continue
        for e in parsed.entries:
            when = _published(e)
            link = e.get("link")
            if link and when and when >= cutoff:
                items[link] = {"url": link, "source": feed["name"], "title": e.get("title", "").strip(),
                               "summary": (e.get("summary") or "")[:500], "published_at": when.isoformat()}
    if not items or not skip_seen:
        return list(items.values())
    seen = set()
    urls = list(items)
    for i in range(0, len(urls), 50):  # PostgREST in.() filter, in chunks
        quoted = ",".join('"' + u.replace('"', '') + '"' for u in urls[i:i + 50])
        seen |= {r["url"] for r in db.select("news_items", {"url": f"in.({quoted})"}, columns="url")}
    return [v for k, v in items.items() if k not in seen]


def score(cfg: dict, items: list[dict], accounts: list[dict]) -> list[dict]:
    """One fast-model call scores every new story. Returns items with score/takeaway/account."""
    listing = "\n".join(f"[{i}] ({it['source']}) {it['title']} :: {it['summary'][:300]}" for i, it in enumerate(items))
    personas = "\n".join(f"- {a['id']}: {a['persona']} ({a['voice'][:120]})" for a in accounts)
    schema = content._obj({"stories": {"type": "array", "items": content._obj({
        "index": {"type": "integer"},
        "score": {"type": "integer"},
        "takeaway": {"type": "string"},
        "reason": {"type": "string"},
        "account": {"type": "string", "enum": [a["id"] for a in accounts]},
    })}})
    prompt = (
        "You filter startup news for Instagram accounts that educate early-stage founders. Score every story "
        "1-10: would an early-stage founder be glad they saw it, AND is there a concrete takeaway they can use? "
        "Be strict: most stories should score 6 or below. 9-10 only for genuinely important, actionable news.\n\n"
        f"ACCEPT:\n{cfg['accept']}\nREJECT:\n{cfg['reject']}\n"
        "takeaway: one line on what founders should learn or do (empty if none). reason: why this score, short.\n"
        f"account: which account's persona fits the story best:\n{personas}\n\nSTORIES:\n{listing}"
    )
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    with client.messages.stream(
        model=llm.model_for(fast=True), max_tokens=16000,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()
    text = next(b.text for b in message.content if b.type == "text")
    for s in json.loads(text)["stories"]:
        if 0 <= s["index"] < len(items):
            items[s["index"]].update(score=s["score"], takeaway=s["takeaway"], reason=s["reason"], account=s["account"])
    return items


def article_text(url: str) -> str:
    try:
        html = requests.get(url, headers=UA, timeout=30).text
    except requests.RequestException:
        return ""
    return trafilatura.extract(html) or ""


def post_params(account: dict, fmt: str, item: dict, article: str) -> dict:
    """Same brief as evergreen posts, plus the article as the only allowed source of facts."""
    params = content.request_params(llm.model_for(fast=False), account, "growth_sales", 1, fmt=fmt)
    task = (
        f"NEWS POST. Write 1 {'carousel' if fmt == 'carousel' else 'reaction Reel script'} about this story "
        f"from {item['source']}.\n"
        "- For this post the ARTICLE below replaces the fact sheet: names and numbers may come ONLY from it. "
        "Put \"article\" in facts_used if you use any.\n"
        "- First say what happened (plainly, in your own words, never copying sentences), then why it matters "
        "for early-stage founders, then what they should do or learn. No speculation beyond the article.\n"
        f"- Suggested takeaway: {item['takeaway']}\n"
        f"- Credit the source in the caption, e.g. 'Source: {item['source']}'.\n"
        "- Pick the topic that fits best.\n\n"
        f"ARTICLE TITLE: {item['title']}\nARTICLE TEXT:\n{article[:12000]}"
    )
    params["messages"] = [{"role": "user", "content": task}]
    return params


def write_post(account: dict, fmt: str, item: dict, article: str) -> dict | None:
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    with client.messages.stream(**post_params(account, fmt, item, article)) as stream:
        message = stream.get_final_message()
    posts = content.parse_posts(message)
    return posts[0] if posts else None


def publish_time(cfg: dict, tz: ZoneInfo) -> datetime:
    """Now, unless it's quiet hours locally; then the end of quiet hours."""
    now = datetime.now(tz)
    start, end = (time(*map(int, t.split(":"))) for t in cfg["quiet_hours"])
    if start <= now.time() < end:
        return datetime.combine(now.date(), end, tz).astimezone(UTC)
    return now.astimezone(UTC)
