"""Builds the AI brief and turns the AI output into post drafts.

The AI decides what a post says plus which background category and music mood fit.
It never picks files; engine.assets does that.
"""
import json

import yaml

from engine import assets
from engine.config import ROOT

TOPICS = {
    "fundraising": "raising money: pre-seed/seed, angels, accelerators, pitch decks, SAFEs, investor outreach",
    "starting_up": "starting a company: validating ideas, incorporation basics, co-founders, first steps, legal basics",
    "finance": "money management: bookkeeping, runway, burn, pricing, unit economics, taxes basics, invoicing",
    "tools_productivity": "tools and workflows: AI tools, meeting assistants, automation, focus, founder routines",
    "growth_sales": "first customers: sales, distribution, marketing on a budget, retention, early traction",
}

HOOK_TYPES = [
    "hot_take", "contrarian", "callout", "myth", "mistake", "warning", "unpopular_opinion",
    "secret", "question", "comparison", "how_to", "list", "story", "checklist", "stat",
]

LIMITS = {
    "carousel": {"hook": 70, "cover_subtitle": 70, "slide_title": 55, "slide_body": 230, "cta": 90, "caption": 1500},
    "reaction": {"hook": 60, "point": 90, "cta": 60, "caption": 1500},
    "animated": {"hook": 60, "point": 70, "cta": 60, "caption": 1500},
    "chat": {"hook": 60, "message": 90, "cta": 60, "caption": 1500, "role": 20},
    "myth_fact": {"hook": 60, "myth": 80, "fact": 110, "cta": 60, "caption": 1500},
    "checklist": {"hook": 60, "item": 60, "cta": 60, "caption": 1500},
    "explainer": {"hook": 70, "say": 110, "cta": 70, "caption": 1500, "words": 120},
}

# Every non-carousel format is a Reel
REEL_FORMATS = ("reaction", "animated", "chat", "myth_fact", "checklist", "explainer")
FORMAT_LABELS = {
    "carousel": "carousel post", "reaction": "reaction Reel script", "animated": "animated text Reel script",
    "chat": "animated chat Reel script", "myth_fact": "myth vs fact Reel script", "checklist": "checklist Reel script",
    "explainer": "narrated explainer Reel script",
}

FORMAT_GUIDES = {
    "carousel": (
        "CAROUSEL: cover (hook + subtitle) -> 4 to 7 value slides (title + body, one idea each) -> CTA slide.\n"
        "Limits (characters): hook {hook}, cover_subtitle {cover_subtitle}, slide title {slide_title}, "
        "slide body {slide_body}, cta {cta}, caption {caption}."
    ),
    "reaction": (
        "REACTION REEL (about 15-20 seconds): opens on a person's reaction clip with the hook written over it, "
        "then 3 to 5 quick text scenes (one punchy line each, read in about 3 seconds), then a short CTA.\n"
        "The hook must make the reaction make sense: a surprising truth, a costly mistake, a myth, or a great shortcut. "
        "POV / 'when you realise' / 'nobody tells you' framings work well. Each point stands alone as one line.\n"
        "reaction: shocked = surprising truth or costly mistake; excited = great hack, shortcut or win; "
        "skeptical = a myth or bad advice being called out.\n"
        "Each point gets its own background category from the menu.\n"
        "Limits (characters): hook {hook}, each point {point}, cta {cta}, caption {caption}."
    ),
    "animated": (
        "ANIMATED TEXT REEL: the hook pops in word by word, then exactly 3 points (one punchy line each), then CTA. "
        "Limits: hook {hook}, each point {point}, cta {cta}."
    ),
    "chat": (
        "CHAT REEL: an animated DM thread between 'you' (the founder) and one other person, other_role = a generic "
        "role like Investor, Mentor, Customer or CA (never a real or named person). 5-6 short messages that feel real "
        "and casual, where the other person reveals the lesson; side is 'you' or 'them'. The hook is shown above the "
        "chat. Limits: hook {hook}, each message {message}, other_role {role}, cta {cta}."
    ),
    "myth_fact": (
        "MYTH VS FACT REEL: exactly 2 pairs. Each myth is something many founders genuinely believe; each fact corrects it "
        "with a concrete reason. Limits: hook {hook}, each myth {myth}, each fact {fact}, cta {cta}."
    ),
    "checklist": (
        "CHECKLIST REEL: a clipboard titled with the hook, then 4-5 items that get ticked off one by one; each item "
        "is a concrete action. Limits: hook {hook}, each item {item}, cta {cta}."
    ),
    "explainer": (
        "NARRATED EXPLAINER REEL (30-45 seconds, spoken by a voiceover): the hook is said first, then 5-7 beats, "
        "then the CTA is said. The whole script (hook + every say + cta) must be under 120 words. Each beat 'say' is ONE short natural spoken sentence (how a person talks, contractions "
        "welcome). emphasis = 1-2 words from that sentence to highlight. gesture = the presenter's pose for that beat (point = points at the illustration, point_up = 'here's the thing', mouth = shocked, facepalm = a painful mistake, phone = checking stats/DMs, think, shrug, explain, thumbs, wink = a cheeky tip, celebrate = a win); vary them. visual = "
        "one UI-style illustration that shows the beat: phone_stats (a profile/stats screen: title, value, label), "
        "stamp (a document stamped with value), counter (a big number counting up), chart (a rising line with "
        "value), chat (an AI/chat box typing title), checklist (items), calendar (value like NOW or a day), cards "
        "(items stacked), versus (items = [before, after]), progress (value as a percent), big_text (value), headline "
        "(a 1-3 word phrase typed in big, e.g. EVERY KIND), editor (a video/doc editor timeline with an error toast: title, "
        "value = error), terminal (items = typed commands, value = result), folder (title, value, items = files), comments "
        "(items = comments), browser (a website: title = headline, value = button, label = url), notifications (title = app, "
        "items = notification texts), app_card (title = app name, value = rating text, label), invoice (title = client, items = "
        "line items, value = total), invite (a calendar invite: title, value = day, label), bank (title, value = balance, items = "
        "spends). Prefer the realistic mockups (editor, terminal, folder, comments, browser, notifications, app_card, invoice, "
        "invite, bank) for most beats. scene = the background: paper for most beats, ink (dark) "
        "for the problem or myth section, accent for the payoff; change scene only 2-3 times per Reel. Keep "
        "visual text very short (value max 12 chars, items max 6 words). Vary the visuals across beats. "
        "Limits: hook {hook}, each say {say}, cta {cta}."
    )
}

SYSTEM_RULES = """You write Instagram carousels and short Reels for faceless educational accounts that help founders.

AUDIENCE
Early-stage and aspiring founders, mostly in India: idea stage to seed, often solo or first-time, short on
time and money. Use Indian context where it fits (UPI, GST, DPIIT, Indian cities), but keep advice useful anywhere.

WHAT GOOD LOOKS LIKE
- Genuinely useful and specific. Every slide teaches one concrete thing the reader can act on.
- A hook that stops the scroll: specific, curiosity-driven, no clickbait the slides can't pay off.
- Plain words, short sentences, no jargon without a one-line explanation.

HARD RULES
- Specific names (investors, funds, accelerators, companies, people) and specific numbers
  (percentages, money amounts, statistics, dates) may ONLY come from the FACT SHEET below.
  List the ids of facts you used in facts_used. If the fact sheet has nothing relevant,
  keep the advice general: no names, no statistics, no money figures. Counting numbers
  like "5 mistakes" or "step 3" are fine.
- NEVER invent stories, people, founders, companies, case studies, quotes or testimonials. No "Imagine Maya..."
  characters. Real stories only come from provided sources. Keep advice concrete: steps, scripts, checklists.
- No guarantees ("guaranteed", "will get you funded", "100%").
- Legal, tax and accounting points are general information; where it matters, tell the reader
  to confirm with an accountant or lawyer for their country.
- Do not mention any product or company of ours. No emojis on slides.
- 3 to 8 hashtags, lowercase, without '#'. Captions add context and end with a question or save prompt.

FORMATS
{formats}

HOOKS: CONTROVERSIAL, WRITTEN LIKE A REAL PERSON REACTING
The hook is the line someone would actually type or say when they hear a surprising founder truth: casual,
lowercase, a bit messy, like a text message or a reaction-video caption. It challenges a belief founders hold.
Good: "wdym it's not necessary to incorporate from day 1??", "wait you DON'T need a co-founder??",
"bro stop building and go sell it first", "no way people still pay for this", "why did nobody tell me investors
don't read the deck", "ok who decided networking events were a good idea".
For reaction Reels the hook must fit the face in the clip: shocked/excited = "wait what / no way / wdym";
skeptical = "be so serious rn / who told you that".
Never write like an AI or a content template: no "Unpopular opinion:", "Hot take:", "POV:", "Here's why",
"Let's talk about", "The truth about", "game-changer", "In today's world", no colons dividing the hook, no
title case, no em dashes. Slides and points stay clear and plain (short sentences, no slang overload).
Rules for controversy: the post must genuinely back the claim; no false claims, no fear-mongering about money
or health, no attacks on real people, companies, groups or professions, no politics or religion.
Hook types available: {hook_types}

ASSET MENU
background (image category): {backgrounds}
- office: workplaces, teams, presenting  - money: cash, coins, savings, growth
- laptop-desk: laptops, desks, studying  - city-travel: skylines, streets, ambition
- abstract-texture: neutral shapes and textures, fits any topic
music_mood (Reels only): {moods}
- calm: advice, how-to  - dramatic: mistakes, warnings, myths  - inspirational: stories, wins  - happy: tools, quick wins
reaction (reaction Reels only): {reactions}

FACT SHEET
{facts}
"""


def load_facts() -> list[dict]:
    data = yaml.safe_load((ROOT / "config" / "facts.yaml").read_text()) or {}
    return data.get("facts") or []


def system_prompt() -> str:
    facts = load_facts()
    facts_text = "\n".join(f"[{f['id']}] {f['fact']}" for f in facts) or "(empty - give general advice only)"
    formats = "\n\n".join(guide.format(**LIMITS[f]) for f, guide in FORMAT_GUIDES.items())
    return SYSTEM_RULES.format(
        formats=formats,
        hook_types=", ".join(HOOK_TYPES),
        backgrounds=", ".join(assets.background_categories()),
        moods=", ".join(assets.music_moods()),
        reactions=", ".join(assets.reaction_emotions()),
        facts=facts_text,
    )


LEARNINGS: list[str] = []  # set by scripts.plan_week from the Sunday review


def account_brief(account: dict, avoid_hooks: list[str], proven_hooks: list[str]) -> str:
    lines = [
        f"ACCOUNT: @{account['handle']} - {account['persona']}",
        f"VOICE: {account['voice']}",
    ]
    if LEARNINGS:
        lines.append("LAST WEEK'S LEARNINGS (from our own numbers; lean into what worked, fix what didn't):")
        lines += [f"- {x}" for x in LEARNINGS]
    if proven_hooks:
        lines.append("PROVEN HOOKS (performed well; write fresh variations of their pattern, never copies):")
        lines += [f"- {h}" for h in proven_hooks]
    if avoid_hooks:
        lines.append("RECENT HOOKS ACROSS ALL ACCOUNTS (do not repeat or closely paraphrase):")
        lines += [f"- {h}" for h in avoid_hooks]
    return "\n".join(lines)


def _obj(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def post_schema(fmt: str) -> dict:
    common = {
        "topic": {"type": "string", "enum": list(TOPICS)},
        "hook_type": {"type": "string", "enum": HOOK_TYPES},
        "hook": {"type": "string"},
    }
    tail = {
        "cta": {"type": "string"},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "facts_used": {"type": "array", "items": {"type": "string"}},
    }
    backgrounds = {"type": "string", "enum": assets.background_categories()}
    if fmt == "carousel":
        slide = _obj({"title": {"type": "string"}, "body": {"type": "string"}})
        post = _obj({
            **common,
            "cover_subtitle": {"type": "string"},
            "slides": {"type": "array", "items": slide},
            "background": backgrounds,
            **tail,
        })
    elif fmt == "reaction":
        point = _obj({"text": {"type": "string"}, "background": backgrounds})
        post = _obj({
            **common,
            "reaction": {"type": "string", "enum": assets.reaction_emotions()},
            "points": {"type": "array", "items": point},
            "music_mood": {"type": "string", "enum": assets.music_moods()},
            **tail,
        })
    elif fmt == "animated":
        point = _obj({"text": {"type": "string"}, "background": backgrounds})
        post = _obj({**common, "points": {"type": "array", "items": point},
                     "music_mood": {"type": "string", "enum": assets.music_moods()}, **tail})
    elif fmt == "chat":
        msg = _obj({"side": {"type": "string", "enum": ["you", "them"]}, "text": {"type": "string"}})
        post = _obj({**common, "other_role": {"type": "string"}, "messages": {"type": "array", "items": msg},
                     "music_mood": {"type": "string", "enum": assets.music_moods()}, **tail})
    elif fmt == "myth_fact":
        pair = _obj({"myth": {"type": "string"}, "fact": {"type": "string"}})
        post = _obj({**common, "pairs": {"type": "array", "items": pair},
                     "music_mood": {"type": "string", "enum": assets.music_moods()}, **tail})
    elif fmt == "explainer":
        from engine.render.explainer import GESTURES, SCENES, VISUALS
        vis = _obj({"type": {"type": "string", "enum": list(VISUALS)}, "title": {"type": "string"},
                    "value": {"type": "string"}, "label": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "string"}}})
        beat = _obj({"say": {"type": "string"}, "emphasis": {"type": "string"},
                     "gesture": {"type": "string", "enum": list(GESTURES)}, "scene": {"type": "string", "enum": list(SCENES)},
                     "visual": vis})
        post = _obj({**common, "beats": {"type": "array", "items": beat},
                     "music_mood": {"type": "string", "enum": assets.music_moods()}, **tail})
    elif fmt == "checklist":
        post = _obj({**common, "items": {"type": "array", "items": {"type": "string"}},
                     "music_mood": {"type": "string", "enum": assets.music_moods()}, **tail})
    else:
        raise ValueError(f"unknown format {fmt}")
    return _obj({"posts": {"type": "array", "items": post}})


def request_params(model: str, account: dict, topic: str, count: int, fmt: str = "carousel",
                   avoid_hooks: list[str] = (), proven_hooks: list[str] = (),
                   angles: list[str] = (), fix_notes: str = "", explore_away_from: list[str] = ()) -> dict:
    """Messages API params for one (account, topic, format) request. Shared system rules come first so they cache."""
    label = FORMAT_LABELS[fmt] + "(s)"
    if angles:
        listed = "\n".join(f"{i}. {a}" for i, a in enumerate(angles, 1))
        task = (f"Write {len(angles)} {label} for this account on the topic '{topic}' ({TOPICS[topic]}), "
                f"one per angle below, in the same order. Vary hook types.\n{listed}")
    else:
        task = (f"Write {count} {label} for this account on the topic '{topic}' "
                f"({TOPICS[topic]}). Each one needs a different angle and, where possible, a different hook type.")
    task += f"\nSet topic to '{topic}' on every post."
    if explore_away_from:
        listed = "\n".join(f"- {h}" for h in explore_away_from)
        task += ("\nEXPLORE: these posts are currently winning. Keep the same hook voice, but deliberately cover a "
                 "DIFFERENT kind of insight than them (e.g. a framework, comparison, tool, how-to, myth, number or "
                 f"behind-the-scenes, rather than another mistake callout):\n{listed}")
    if fix_notes:
        task += f"\nA previous attempt failed automatic checks: {fix_notes}. Avoid these problems."
    return {
        "model": model,
        "max_tokens": 32000,
        "output_config": {"effort": "medium", "format": {"type": "json_schema", "schema": post_schema(fmt)}},
        "system": [
            {"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": account_brief(account, list(avoid_hooks), list(proven_hooks))},
        ],
        "messages": [{"role": "user", "content": task}],
    }


SOURCED_GUIDES = {
    "reddit_qa": (
        "FOUNDER QUESTION. A real founder asked this on r/{sub} this week:\n{source}\n\n"
        "Write a post that answers it for everyone with the same problem. The hook is a controversial take on the "
        "question (e.g. 'wait you don't even need a co-founder??'), backed up by the answer. Don't quote the person or mention usernames. "
        "Give concrete, practical steps. Specific names and numbers only if they appear in the question. "
        "In the caption, say it came from a founder question on Reddit (r/{sub})."
    ),
    "breakdown": (
        "REAL COMPANY BREAKDOWN: {label}. Use ONLY the source below for names, numbers, dates and events; "
        "never invent quotes, figures or events. Structure: hook on the most surprising decision or turn -> "
        "what they did -> the turning point -> 2-3 lessons early-stage founders can copy. "
        "Hook: a provocative take on the story (e.g. 'they had the better product and STILL lost??'). Credit the source in the caption ('Source: {source_name}').\n\nSOURCE:\n{source}"
    ),
    "india_admin": (
        "INDIA STARTUP GUIDE: {label}. Use ONLY the sources below; names and figures (amounts, %, limits, dates, "
        "deadlines) must come from them. If sources give different figures for the same thing, leave that figure "
        "out. KEEP IT SHORT: exactly 4 slides or Reel points (what it is, who qualifies, the benefit, how to apply), "
        "each under 140 characters; drop everything else. Hook: a provocative take, e.g. 'wdym the govt just gives startups this money??'. Do not tell readers to verify with a portal or a CA. "
        "Put \"sources\" in facts_used if you use any figure.\n\n{source}"
    ),
    "funding_roundup": (
        "WEEKLY FUNDING ROUNDUP ({label}). From the headlines below, pick the 4-6 most interesting startup "
        "rounds, preferring Indian early-stage companies. One slide per round: company, amount, and what the "
        "headline says they do. Last slide: 2-3 patterns founders can learn from this week (sectors, stages). "
        "Use ONLY facts in the headlines; never add investors or details they don't state. "
        "Put \"sources\" in facts_used.\n\nHEADLINES:\n{source}"
    ),
    "promo": (
        "PROMO FOR OUR OWN FREE TOOL: {label}. This post promotes it openly; it's ours (built by Beesz), so no fake "
        "testimonials, no invented users, results or numbers. Use ONLY the facts below. ANGLE: {angle}.\n"
        "Hook: a real person reacting, e.g. 'wait the reply guys are the ones getting customers??' (never sound like an ad). "
        "Points: 3-4 lines: the founder problem -> what the tool is -> what counts / why it works -> how to join. "
        "Don't quote live counts or rankings (the video shows the live board). The site is opened on a laptop "
        "(Chrome extension), so the CTA tells people to save this and grab the link in bio, e.g. 'Link in bio. "
        "Save this for your laptop'. Caption: 2-4 short lines, mention {url} and that the link is in the bio. "
        "facts_used: [\"sources\"].\n\nFACTS:\n{source}"
    ),
}


def sourced_params(model: str, account: dict, fmt: str, doc: dict, fix_notes: str = "") -> dict:
    """Request params for a post written from real source material (no fact sheet, no invention)."""
    params = request_params(model, account, "starting_up", 1, fmt=fmt)
    if len(doc["texts"]) > 1:
        source = "\n\n".join(f"SOURCE {i} ({url}):\n{text}" for i, (url, text)
                              in enumerate(zip(doc["urls"], doc["texts"]), 1))
    else:
        source = doc["texts"][0]
    label = FORMAT_LABELS[fmt]
    task = f"Write 1 {label}. Pick the topic that fits best.\n" + SOURCED_GUIDES[doc["kind"]].format(
        source=source, label=doc.get("label", ""), sub=doc.get("sub", ""),
        source_name=doc.get("source_name", ""), official=doc.get("official", "the official portal"),
        angle=doc.get("angle", ""), url=doc.get("url", ""))
    if doc.get("previous_hooks"):
        task += ("\n\nWe already posted about this before. Take a clearly DIFFERENT angle and lesson than these:\n"
                 + "\n".join(f"- {h}" for h in doc["previous_hooks"]))
    if fix_notes:
        task += f"\n\nA previous attempt failed automatic checks: {fix_notes}. Avoid these problems."
    params["messages"] = [{"role": "user", "content": task}]
    return params


def winner_params(model: str, account: dict, fmt: str, count: int, winners: list[dict],
                  avoid_hooks: list[str] = (), fix_notes: str = "") -> dict:
    """Posts that reuse the PATTERN behind current winners on new topics (the 'exploit' share of the plan)."""
    params = request_params(model, account, "starting_up", count, fmt=fmt, avoid_hooks=avoid_hooks)
    listed = "\n".join(
        f"- \"{w['hook']}\" ({w.get('hook_type')}, {w.get('topic')}, "
        + ("a reference the owner wants more of)" if w.get("source") == "reference" else f"{w.get('views')} views)")
        for w in winners)
    task = (f"Write {count} {FORMAT_LABELS[fmt]}(s). These are our current winners and the owner's references:\n{listed}\n\n"
            "Work out WHY they won (the kind of insight, the tension in the hook, how specific it is) and apply "
            "that same pattern to NEW topics founders care about. Never reuse their topics or paraphrase their "
            "hooks. Each post a different topic. Pick the topic field that fits each post.")
    if fix_notes:
        task += f"\nA previous attempt failed automatic checks: {fix_notes}. Avoid these problems."
    params["messages"] = [{"role": "user", "content": task}]
    return params


def plan_entry_params(model: str, account: dict, g: dict, avoid: list[str], proven: list[str],
                      fix_notes: str = "", index: int | None = None) -> dict:
    """Request params for one weekly-plan entry (or one post of it, when rewriting after failed checks)."""
    kind = g.get("kind", "evergreen")
    if kind == "winner":
        count = 1 if index is not None else len(g["slots"])
        return winner_params(model, account, g["format"], count, g["winners"], avoid, fix_notes)
    if kind == "evergreen":
        angles = [g["angles"][index]] if index is not None else g["angles"]
        # Advice posts outside the winner share explore other kinds of insight (40% exploit / 60% explore)
        return request_params(model, account, g["topic"], len(angles), fmt=g["format"], avoid_hooks=avoid,
                              angles=angles, fix_notes=fix_notes, explore_away_from=proven[:6])
    return sourced_params(model, account, g["format"], g["doc"], fix_notes=fix_notes)


def parse_posts(message) -> list[dict]:
    text = next((b.text for b in message.content if b.type == "text"), "")
    return json.loads(text)["posts"] if text else []
