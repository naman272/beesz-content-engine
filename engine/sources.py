"""Real-world source material for post types that must not be invented.

Each function returns "docs": {kind, label, urls, texts, source_url, ...}. The post is written from the
doc's texts, and the checks verify every figure against them.
"""
import html
import json
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import anthropic
import feedparser
import httpx2
import requests
import trafilatura
import yaml

from engine import content, db, llm
from engine.config import ROOT, env

UTC = ZoneInfo("UTC")
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/126 Safari/537.36"}
REDDIT_UA = {"User-Agent": "Mozilla/5.0 (compatible; BeeszContentBot/1.0)"}
MAX_SOURCE_CHARS = 12000


def settings() -> dict:
    return yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())


def fetch_text(url: str) -> str:
    try:
        r = requests.get(url, headers=BROWSER_UA, timeout=30)
    except requests.RequestException:
        return ""
    if r.status_code != 200:
        return ""
    return (trafilatura.extract(r.text) or "")[:MAX_SOURCE_CHARS]


def _used_source_urls(days: int) -> set[str]:
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    rows = db.select("posts", {"created_at": f"gte.{since}", "source_url": "not.is.null"}, columns="source_url")
    return {r["source_url"] for r in rows}


def _previous_hooks(source_url: str) -> list[str]:
    """Hooks we already posted from this source, so a repeat takes a different angle."""
    return [r["hook"] for r in db.select("posts", {"source_url": f"eq.{source_url}", "status": "neq.dropped"},
                                         columns="hook", limit=10)]


def _fast_json(prompt: str, schema: dict, attempts: int = 3) -> dict:
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    for attempt in range(attempts):
        try:
            with client.messages.stream(
                model=llm.model_for(fast=True), max_tokens=16000,
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                message = stream.get_final_message()
            return json.loads(next(b.text for b in message.content if b.type == "text"))
        except (anthropic.APIConnectionError, anthropic.APIStatusError, httpx2.TransportError, OSError) as e:
            # A dropped connection mid-stream isn't retried by the SDK
            if attempt == attempts - 1:
                raise
            print(f"fast model call failed ({type(e).__name__}), retrying")
            time.sleep(10 * (attempt + 1))


# ---------- 1. Founder questions from Reddit ----------

def _reddit_feed(sub: str, tries: int = 4, timeout: int = 30) -> list:
    url = f"https://www.reddit.com/r/{sub}/top/.rss?t=week"
    status = None
    for attempt in range(tries):  # Reddit rate-limits cloud servers and sometimes hangs; back off and retry
        try:
            r = requests.get(url, headers=REDDIT_UA, timeout=timeout)
            status = r.status_code
            if r.status_code == 200:
                return feedparser.parse(r.content).entries
        except requests.RequestException as e:  # one slow subreddit must not sink the whole plan
            status = type(e).__name__
        if attempt < tries - 1:
            time.sleep(30)
    print(f"reddit r/{sub}: gave up ({status})")
    return []


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(value or ""))
    text = re.sub(r"submitted by .*", "", text, flags=re.S)
    return re.sub(r"\s+", " ", text).strip()


# Reddit blocks GitHub's servers part of the time, so threads are collected a few subreddits per hour all week
# (scripts.scheduler -> collect_reddit) into a pool on R2; the Sunday plan reads the pool plus one quick live pass.
REDDIT_POOL = "pools/reddit.json"
POOL_DAYS = 10


def _reddit_threads(sub: str, min_chars: int, **kw) -> list[dict]:
    out = []
    for e in _reddit_feed(sub, **kw):
        body = _strip_html((e.get("content") or [{}])[0].get("value", ""))
        if e.get("link") and len(e.get("title", "")) + len(body) >= min_chars:
            out.append({"sub": sub, "url": e["link"], "title": e.get("title", ""), "body": body[:3000], "at": time.time()})
    return out


def _load_pool() -> list[dict]:
    from engine import storage
    try:
        pool = json.loads(storage.download(REDDIT_POOL, attempts=2))
    except Exception:
        return []
    return [p for p in pool if p.get("at", 0) >= time.time() - POOL_DAYS * 86400]


def _ask_hn(min_chars: int) -> list[dict]:
    """Ask HN questions from the last week (Hacker News's API doesn't block servers, unlike Reddit)."""
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search_by_date", timeout=20, params={
            "tags": "ask_hn", "hitsPerPage": 100,
            "numericFilters": f"created_at_i>{int(time.time()) - 7 * 86400},points>5"})
        hits = r.json()["hits"]
    except Exception as e:
        print(f"ask hn: failed ({type(e).__name__})")
        return []
    out = []
    for h in hits:
        body = _strip_html(h.get("story_text") or "")
        if len(h.get("title") or "") + len(body) >= min_chars:
            out.append({"sub": "Ask HN", "url": f"https://news.ycombinator.com/item?id={h['objectID']}",
                        "title": h["title"], "body": body[:3000], "at": time.time()})
    return out


def collect_reddit(per_run: int = 3) -> int:
    """Adds this hour's few subreddits to the pool (one quick try each). Returns threads added."""
    from engine import storage
    cfg = settings()["reddit"]
    subs = cfg["subreddits"]
    hour = int(time.time() // 3600)
    picks = [subs[(hour * per_run + i) % len(subs)] for i in range(per_run)]
    pool = _load_pool()
    seen = {p["url"] for p in pool}
    added = 0
    found = [t for sub in picks for t in _reddit_threads(sub, cfg["min_chars"], tries=1, timeout=20)]
    found += _ask_hn(cfg["min_chars"])
    for t in found:
        if True:
            if t["url"] not in seen:
                pool.append(t)
                seen.add(t["url"])
                added += 1
    storage.upload_bytes(REDDIT_POOL, json.dumps(pool).encode(), "application/json")
    print(f"reddit pool: +{added} from {', '.join(picks)} ({len(pool)} threads)")
    return added


def reddit_questions(count: int) -> list[dict]:
    cfg = settings()["reddit"]
    posts = _load_pool()
    seen = {p["url"] for p in posts}
    print(f"reddit pool: {len(posts)} threads")
    for sub in cfg["subreddits"]:  # one quick live pass on top, without long back-offs
        posts += [t for t in _reddit_threads(sub, cfg["min_chars"], tries=1, timeout=15) if t["url"] not in seen]
        time.sleep(3)
    if not posts:
        return []
    known = set()
    for i in range(0, len(posts), 50):
        quoted = ",".join('"' + p["url"].replace('"', "") + '"' for p in posts[i:i + 50])
        known |= {r["url"] for r in db.select("news_items", {"url": f"in.({quoted})"}, columns="url")}
    posts = [p for p in posts if p["url"] not in known]
    print(f"reddit: {len(posts)} new threads")

    schema = content._obj({"threads": {"type": "array", "items": content._obj({
        "index": {"type": "integer"}, "score": {"type": "integer"},
        "question": {"type": "string"}, "reason": {"type": "string"},
    })}})
    scored = []
    for start in range(0, len(posts), 60):
        chunk = posts[start:start + 60]
        listing = "\n".join(f"[{i}] {p['sub']}: {p['title']} :: {p['body'][:400]}" for i, p in enumerate(chunk))
        result = _fast_json(
            "These are this week's top Reddit threads. Score each 1-10: is it a GENUINE question or problem that "
            "many early-stage founders or small business owners share, which we can answer with solid, practical "
            "advice in an Instagram post? High scores: real struggles (first customers, pricing, co-founders, "
            "fundraising, hiring, burnout, using AI/automation to run the business). Low scores: promotions, "
            "'I hit $X MRR' brag posts, product launches, rants with no question, memes, AI industry news, "
            "hiring/job posts, anything needing personal legal or medical advice. Be strict; most score below 6.\n"
            "question: the core question rephrased in one neutral line (no usernames).\n\n" + listing,
            schema,
        )
        for t in result["threads"]:
            if 0 <= t["index"] < len(chunk):
                scored.append({**chunk[t["index"]], **t})
    if scored:
        db.upsert("news_items", [{"url": s["url"], "source": "Ask HN" if s["sub"] == "Ask HN" else f"r/{s['sub']}", "title": s["title"][:500],
                                  "score": s["score"], "takeaway": s["question"], "reason": s["reason"]}
                                 for s in scored], on_conflict="url")
    best = sorted((s for s in scored if s["score"] >= cfg["min_score"]), key=lambda s: -s["score"])
    return [{
        "kind": "reddit_qa", "label": s["question"], "sub": s["sub"], "source_url": s["url"],
        "where": "Hacker News (Ask HN)" if s["sub"] == "Ask HN" else f"Reddit (r/{s['sub']})",
        "urls": [s["url"]], "texts": [f"{s['title']}\n{s['body']}"],
    } for s in best[:count]]


# ---------- 3. Real company breakdowns ----------

def breakdowns(count: int) -> list[dict]:
    cfg = settings()["breakdowns"]
    used = _used_source_urls(cfg["reuse_after_days"])
    docs = []

    # Recent news stories about one company's journey come first (timely)
    since = (datetime.now(UTC) - timedelta(days=14)).isoformat()
    news = [n for n in db.select("news_items", {"created_at": f"gte.{since}", "score": "gte.5", "post_id": "is.null"},
                                 columns="url,source,title", order="score.desc", limit=80)
            if not n["source"].startswith("r/") and n["url"] not in used]
    if news:
        listing = "\n".join(f"[{i}] ({n['source']}) {n['title']}" for i, n in enumerate(news))
        schema = content._obj({"picks": {"type": "array", "items": content._obj({
            "index": {"type": "integer"}, "company": {"type": "string"}})}})
        picks = _fast_json(
            "Pick the stories that are about ONE specific company's journey, decision, pivot, growth or failure, "
            "with a clear lesson early-stage founders can use, AND where the company is one most Indian founders "
            "would recognise (a well-known startup or brand, or a big global name) or the story is unusually "
            "dramatic (a collapse, scandal, huge loss, shock exit). Skip small startups few founders have heard of, "
            "generic market news, interviews about investing, and roundups.\n\n" + listing, schema)["picks"]
        for p in picks:
            if len(docs) >= count or not 0 <= p["index"] < len(news):
                continue
            n = news[p["index"]]
            text = fetch_text(n["url"])
            if len(text) >= cfg["min_chars"]:
                docs.append({"kind": "breakdown", "label": p["company"], "source_name": n["source"],
                             "source_url": n["url"], "urls": [n["url"]], "texts": [f"{n['title']}\n{text}"]})

    # Then well-known companies from Wikipedia: unused ones first, then the least recently used
    # (a repeat gets the earlier hooks, so it takes a different angle)
    last_used = {}
    for r in db.select("posts", {"source_url": "not.is.null"}, columns="source_url,created_at"):
        last_used[r["source_url"]] = max(last_used.get(r["source_url"], ""), r["created_at"])
    companies = sorted(cfg["companies"], key=lambda c: last_used.get(c["url"], ""))
    for c in companies:
        if len(docs) >= count:
            break
        text = fetch_text(c["url"])
        if len(text) >= cfg["min_chars"]:
            docs.append({"kind": "breakdown", "label": c["name"], "source_name": "Wikipedia",
                         "source_url": c["url"], "urls": [c["url"]], "texts": [text],
                         "previous_hooks": _previous_hooks(c["url"])})
    return docs


# ---------- 4. Indian startup admin and government schemes ----------

def india_topics(count: int) -> list[dict]:
    cfg = settings()["india_admin"]
    # Unused topics first, then the least recently covered (each at most once per plan; repeats get the earlier
    # hooks so they take a different angle)
    last_used = {}
    for r in db.select("posts", {"source_url": "like.topic:*"}, columns="source_url,created_at"):
        last_used[r["source_url"]] = max(last_used.get(r["source_url"], ""), r["created_at"])
    docs = []
    for topic in sorted(cfg["topics"], key=lambda t: last_used.get(f"topic:{t['id']}", "")):
        if len(docs) >= count:
            break
        marker = f"topic:{topic['id']}"
        texts, urls = [], []
        for url in topic["sources"]:
            text = fetch_text(url)
            if len(text) >= 800:
                texts.append(text)
                urls.append(url)
        if len(texts) >= cfg["min_sources"]:
            docs.append({"kind": "india_admin", "label": topic["title"], "official": topic["official"],
                         "source_url": marker, "urls": urls, "texts": texts, "previous_hooks": _previous_hooks(marker)})
        else:
            print(f"india topic {topic['id']}: only {len(texts)} readable sources, skipped")
    return docs


# ---------- 5. Weekly funding roundup ----------

def funding_roundup(week_start: str) -> dict | None:
    cfg = settings()["funding_roundup"]
    since = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    items = [n for n in db.select("news_items", {"created_at": f"gte.{since}"}, columns="source,title,url")
             if not n["source"].startswith("r/")]
    if not items:
        return None
    listing = "\n".join(f"[{i}] ({n['source']}) {n['title']}" for i, n in enumerate(items))
    schema = content._obj({"rounds": {"type": "array", "items": content._obj({"index": {"type": "integer"}})}})
    picks = _fast_json("Which of these headlines announce a startup funding round (company raised money)? "
                       "Return their indexes.\n\n" + listing, schema)["rounds"]
    rounds = [items[p["index"]] for p in picks if 0 <= p["index"] < len(items)]
    if len(rounds) < cfg["min_rounds"]:
        print(f"funding roundup: only {len(rounds)} rounds this week, skipped")
        return None
    text = "\n".join(f"- {r['title']} ({r['source']})" for r in rounds)
    return {"kind": "funding_roundup", "label": f"Startup funding, week of {week_start}",
            "source_url": f"roundup:{week_start}", "urls": [r["url"] for r in rounds], "texts": [text]}
