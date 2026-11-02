"""Reads links/videos the owner sends to the Telegram group, analyses them as content references, saves them
for the weekly plan and replies to each message. Runs every few hours (polling, no webhook).

Telegram keeps unconfirmed updates for 24 hours; confirming them (offset) tells it they're handled.

Run: python -m scripts.telegram_inbox
"""
import base64
import json
import re
import subprocess
import tempfile
from pathlib import Path

import anthropic
import requests

from engine import content, db, llm, telegram
from engine.config import env
from engine.sources import fetch_text

URL = re.compile(r"(?:https?://|www\.|(?:instagram|youtube|youtu|tiktok)\.(?:com|be)/)\S+")


def updates() -> list[dict]:
    return telegram._call("getUpdates", json={"timeout": 0})


def confirm(last_update_id: int) -> None:
    telegram._call("getUpdates", json={"offset": last_update_id + 1, "timeout": 0})


def reply(message: dict, text: str) -> None:
    telegram._call("sendMessage", json={"chat_id": env("TELEGRAM_CHAT_ID"), "text": text[:4096],
                                        "reply_to_message_id": message["message_id"]})


def download_link(url: str, folder: Path) -> tuple[Path | None, str]:
    """Video (if downloadable) plus its caption/description."""
    out = folder / "video.mp4"
    meta = subprocess.run(["yt-dlp", "--no-warnings", "-f", "mp4/best[height<=1080]", "-o", str(out),
                           "--print-json", "--no-simulate", url], capture_output=True, text=True, timeout=180)
    caption = ""
    if meta.stdout.strip():
        try:
            info = json.loads(meta.stdout.strip().splitlines()[-1])
            caption = (info.get("description") or info.get("title") or "")[:2000]
        except ValueError:
            pass
    return (out if out.exists() else None), caption


def download_telegram_file(file_id: str, folder: Path) -> Path | None:
    info = telegram._call("getFile", json={"file_id": file_id})  # bots can fetch files up to 20 MB
    data = requests.get(f"https://api.telegram.org/file/bot{env('TELEGRAM_BOT_TOKEN')}/{info['file_path']}", timeout=120)
    path = folder / "upload.mp4"
    path.write_bytes(data.content)
    return path


def frames(video: Path, folder: Path, count: int = 4) -> list[Path]:
    paths = []
    for i, t in enumerate((0.5, 2.0, 5.0, 9.0)[:count]):
        p = folder / f"f{i}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1",
                        "-vf", "scale=540:-2", str(p)], capture_output=True)
        if p.exists():
            paths.append(p)
    return paths


def analyse(note: str, url: str, caption: str, page_text: str, images: list[Path]) -> dict:
    schema = content._obj({
        "hook": {"type": "string"}, "hook_type": {"type": "string", "enum": content.HOOK_TYPES},
        "format": {"type": "string", "enum": ["carousel", *content.REEL_FORMATS]},
        "topic": {"type": "string", "enum": list(content.TOPICS)},
        "why_it_works": {"type": "string"}, "how_we_use_it": {"type": "string"},
    })
    blocks = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                           "data": base64.b64encode(p.read_bytes()).decode()}} for p in images]
    blocks.append({"type": "text", "text": (
        "The owner of 5 founder-education Instagram accounts sent this as a reference for what kind of content to "
        "post. Work out the hook (the opening line or on-screen text), the hook style, which of our formats it is "
        "closest to, why it works, and how we should use the PATTERN (never copy the content).\n"
        f"Owner's note: {note or '(none)'}\nLink: {url or '(uploaded video)'}\nCaption: {caption or '(unavailable)'}\n"
        f"Page text: {page_text[:3000] or '(unavailable)'}\nFrames attached: {len(images)}")})
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=llm.model_for(fast=True), max_tokens=4000,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": blocks}])
    return json.loads(next(b.text for b in message.content if b.type == "text"))


def handle(message: dict) -> None:
    text = message.get("text") or message.get("caption") or ""
    urls = URL.findall(text)
    if not urls and not message.get("video") and not message.get("document") and len(text) > 20:
        # A plain note describing content is a reference too
        card = analyse(text, "", "", text, [])
        db.insert("hooks", {"hook": card["hook"][:500], "hook_type": card["hook_type"], "format": card["format"],
                            "topic": card["topic"], "source": "reference", "active": True})
        reply(message, f"✅ Noted for next week's plan.\nIdea: {card['hook']}\nHow we'll use it: {card['how_we_use_it']}")
        return
    video_file = (message.get("video") or {}).get("file_id") or (
        (message.get("document") or {}).get("file_id") if "video" in (message.get("document") or {}).get("mime_type", "") else None)
    if not urls and not video_file:
        return
    note = URL.sub("", text).strip()
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        url = urls[0] if urls else ""
        video, caption, page_text = None, "", ""
        if video_file:
            video = download_telegram_file(video_file, folder)
        elif re.search(r"instagram\.com|youtube\.com|youtu\.be|tiktok\.com", url):
            video, caption = download_link(url, folder)
        else:
            page_text = fetch_text(url)
        if url and not url.startswith("http"):
            url = "https://" + url
        images = frames(video, folder) if video else []
        print(f"message {message['message_id']}: url={url[:80]!r} upload={bool(video_file)} video={bool(video)} "
              f"frames={len(images)} caption={len(caption)} page_text={len(page_text)}")
        if not images and not caption and not page_text:
            reply(message, "⚠️ I couldn't open this one (the video didn't download and there was no caption or page "
                           "text to read). Send the video file itself here, or a line describing what you liked.")
            return
        card = analyse(note, url, caption, page_text, images)
    db.insert("hooks", {"hook": card["hook"][:500], "hook_type": card["hook_type"], "format": card["format"],
                        "topic": card["topic"], "source": "reference", "active": True})
    seen = "video analysed" if images else ("caption only, video not downloadable; send the file for a full read" if url and not page_text else "page text")
    reply(message, f"✅ Added to next week's plan as a reference ({seen}).\n\nHook: {card['hook']}\n"
                   f"Style: {card['hook_type']} · Closest format: {card['format']} · Topic: {card['topic']}\n"
                   f"Why it works: {card['why_it_works']}\nHow we'll use it: {card['how_we_use_it']}")


def main() -> None:
    chat = str(env("TELEGRAM_CHAT_ID"))
    items = updates()
    print(f"{len(items)} updates")
    for u in items:
        message = u.get("message") or u.get("channel_post") or {}
        if str(message.get("chat", {}).get("id")) != chat or message.get("from", {}).get("is_bot"):
            continue
        try:
            handle(message)
        except Exception as e:
            print(f"failed on message {message.get('message_id')}: {e}")
            reply(message, f"⚠️ Couldn't analyse this one ({type(e).__name__}). Try sending the video file directly.")
    if items:
        confirm(items[-1]["update_id"])


if __name__ == "__main__":
    main()
