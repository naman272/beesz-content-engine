"""Writes one post per account, renders it and sends it to Telegram. Nothing is posted to Instagram.

Run: python -m scripts.preview                       # carousel for every account
     python -m scripts.preview acc1 --reaction       # reaction Reel for one account
     python -m scripts.preview acc5 acc1 --promo      # own-product promo Reel (config/promos.yaml)
     python -m scripts.preview --reuse               # re-render the last AI output (no AI cost)
"""
import json
import random
import sys

import anthropic

from engine import assets, checks, content, llm, produce, promos, telegram
from engine.config import ROOT, env, load_accounts
from engine.render import carousel, reaction

OUT = ROOT / "output" / "preview"


def write_post(account: dict, fmt: str, doc: dict | None = None) -> dict:
    topic = random.choice(list(content.TOPICS))
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    if doc:
        params = content.sourced_params(llm.model_for(fast=False), account, fmt, doc)
    else:
        params = content.request_params(llm.model_for(fast=False), account, topic, count=1, fmt=fmt)
    with client.messages.stream(**params) as stream:
        message = stream.get_final_message()
    print(f"  tokens: in {message.usage.input_tokens}, out {message.usage.output_tokens}")
    return content.parse_posts(message)[0]


def caption_text(post: dict) -> str:
    return post["caption"] + "\n\n" + " ".join(f"#{h}" for h in post["hashtags"])


def preview_carousel(account: dict, post: dict, out) -> str:
    bg = assets.pick_background(post["background"], account.get("background_style", "any"))
    slides = carousel.render(post, account, bg, out / "slides")
    telegram.send_photos(slides, caption_text(post))
    return f"bg: {post['background']}"


def preview_reaction(account: dict, post: dict, out) -> str:
    clip = assets.pick_reaction(post["reaction"])
    used = set()
    backgrounds = []
    for point in post["points"]:
        bg = assets.pick_background(point["background"], account.get("background_style", "any"), avoid=used)
        used.add(bg["file"])
        backgrounds.append(bg)
    music = assets.pick_music(post["music_mood"])
    video = reaction.render(post, account, clip, backgrounds, assets.path(music["file"]), out / "reaction.mp4")
    telegram.send_video(video, caption_text(post))
    return f"reaction: {clip['file']} · music: {music['title']} - {music['artist']}"


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fmt = "reaction" if "--reaction" in sys.argv else "carousel"
    for a in sys.argv:
        if a.startswith("--format="):
            fmt = a.split("=", 1)[1]
    accounts = [a for a in load_accounts()["accounts"] if not args or a["id"] in args]
    promo_docs = []
    if "--promo" in sys.argv:
        fmt = "reaction"
        promo = promos.load()[0]
        promo_docs = promos.docs(promo, len(accounts))

    for n, account in enumerate(accounts):
        doc = promo_docs[n] if promo_docs else None
        out = OUT / account["id"] / fmt
        post_file = out / "post.json"
        print(f"@{account['handle']} ({fmt})")
        if "--reuse" in sys.argv and post_file.exists():
            post = json.loads(post_file.read_text())
        else:
            post = write_post(account, fmt, doc)
            out.mkdir(parents=True, exist_ok=True)
            post_file.write_text(json.dumps(post, indent=2))

        problems = (checks.check_post(post, fmt, source_texts=doc["texts"], promo=True) if doc
                    else checks.check_post(post, fmt))
        status = "✅ passed checks" if not problems else "⚠️ " + "; ".join(problems)
        telegram.send_message(f"PREVIEW {fmt} · @{account['handle']} ({account['persona']})\n"
                              f"{post['topic']} · {post['hook_type']}\n{status}")
        if doc:
            row = {"id": f"preview-{account['id']}-promo", "content": post, "format": fmt, "kind": "promo",
                   "source_url": doc["url"]}
            files, used = produce.render(row, account)
            telegram.send_video(files[0], caption_text(post))
            details = f"angle: {doc['angle']} · reaction: {used['reaction']}"
        elif fmt == "reaction":
            details = preview_reaction(account, post, out)
        elif fmt == "carousel":
            details = preview_carousel(account, post, out)
        else:
            files, used = produce.render({"id": f"preview-{account['id']}-{fmt}", "content": post, "format": fmt}, account)
            telegram.send_video(files[0], caption_text(post))
            details = f"music: {used.get('music_credit')}"
        print(f"  sent ({status}) {details}")


if __name__ == "__main__":
    main()
