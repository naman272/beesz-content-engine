"""Explainer Reel: narrated voiceover, captions synced 2-4 words at a time, a gesturing presenter and a new
animated UI-style illustration on every beat. Paper look: off-white, black ink, one accent colour.

Script fields (format "explainer"): hook, beats [{say, emphasis, gesture, visual {type, title, value, label,
items}}], cta, music_mood. The hook and cta are spoken too. Rendered with HyperFrames.
"""
import html
import math
import re
from pathlib import Path

from engine import voice
from engine.render.animated import _font_faces, render_project
from engine.render.mascot import LOOKS, character

VISUALS = ("phone_stats", "stamp", "counter", "chart", "chat", "checklist", "calendar", "cards", "versus",
           "progress", "big_text", "headline")
SCENES = ("paper", "ink", "accent")
GESTURES = ("point", "explain", "shrug", "mouth", "thumbs", "celebrate", "think")
# Accent colours that read well on paper (the account accents are tuned for dark backgrounds)
PAPER_ACCENT = {"acc1": "#E63946", "acc2": "#C8763A", "acc3": "#1E6FD9", "acc4": "#7B2FF7", "acc5": "#D62828"}
PAPER, INK = "#EFEDE8", "#141414"


def _e(text) -> str:
    return html.escape(str(text or "").strip())


def chunks(line: str, size: int = 3) -> list[str]:
    """Caption chunks of 2-4 words, breaking after punctuation where possible."""
    words, out, cur = line.split(), [], []
    for w in words:
        cur.append(w)
        if len(cur) >= size + 1 or (len(cur) >= 2 and re.search(r"[,.?!:;]$", w)):
            out.append(" ".join(cur)); cur = []
    if cur:
        if out and len(cur) == 1:
            out[-1] += " " + cur[0]
        else:
            out.append(" ".join(cur))
    return out


def _caption_html(chunk: str, emphasis: list[str]) -> str:
    out = []
    for w in chunk.split():
        bare = re.sub(r"[^\w']", "", w).lower()
        hot = any(bare and bare in re.sub(r"[^\w' ]", "", e).lower().split() for e in emphasis)
        out.append(f'<span class="cw{" em" if hot else ""}">{_e(w)}</span>')
    return " ".join(out)


def _num(value: str) -> tuple[str, float | None, str]:
    """Split '39.5K' into ('', 39.5, 'K') so counters can count up; non-numbers return None."""
    m = re.match(r"^([^\d]*)(\d+(?:\.\d+)?)(.*)$", str(value or "").strip())
    return (m.group(1), float(m.group(2)), m.group(3)) if m else ("", None, str(value or ""))


def visual(i: int, v: dict, accent: str) -> tuple[str, list[str], float]:
    """HTML for one illustration plus its own animation lines (relative to beat start, as offsets)."""
    t, title, value, label = v.get("type", "big_text"), _e(v.get("title")), _e(v.get("value")), _e(v.get("label"))
    items = [_e(x) for x in (v.get("items") or [])][:5]
    vid = f"v{i}"
    js = []
    if t == "phone_stats":
        pre, n, suf = _num(v.get("value"))
        body = f'''<div class="phone"><div class="notch"></div><div class="ph-head"><div class="ph-av"></div>
          <div><div class="ph-name">{title or "your startup"}</div><div class="ph-sub">{label or "this week"}</div></div></div>
          <div class="ph-big"><span class="count" data-to="{n if n is not None else ''}">{value}</span></div>
          <div class="ph-bars">{"".join(f'<div class="ph-bar" style="height:{30 + (k * 37) % 90}px"></div>' for k in range(7))}</div></div>'''
        js.append(f'tl.fromTo("#{vid} .ph-bar", {{scaleY: 0}}, {{scaleY: 1, duration: 0.4, stagger: 0.06, transformOrigin: "50% 100%"}}, AT + 0.3);')
    elif t == "stamp":
        body = f'''<div class="card doc"><div class="doc-t">{title}</div>{"".join(f'<div class="doc-l">{x}</div>' for x in items[:3]) or '<div class="doc-l"></div><div class="doc-l short"></div>'}
          <div class="stampmark">{value or "NOTED"}</div></div>'''
        js.append(f'tl.fromTo("#{vid} .stampmark", {{scale: 2.6, opacity: 0, rotation: -24}}, {{scale: 1, opacity: 1, rotation: -12, duration: 0.22, ease: "power4.in"}}, AT + 0.5);')
        js.append(f'tl.to("#{vid} .card", {{x: 10, duration: 0.05, repeat: 3, yoyo: true}}, AT + 0.72);')
    elif t == "counter":
        pre, n, suf = _num(v.get("value"))
        body = f'''<div class="card counterbox"><div class="ctr-l">{title}</div>
          <div class="ctr">{_e(pre)}<span class="count" data-to="{n if n is not None else ''}">{value if n is None else 0}</span>{_e(suf)}</div>
          <div class="ctr-s">{label}</div></div>'''
    elif t == "chart":
        body = f'''<div class="card chartbox"><div class="ch-t">{title}</div><div class="ch-v">{value}</div>
          <svg viewBox="0 0 600 260" class="ch-svg"><path class="ch-line" d="M10 240 C 120 230, 200 210, 270 170 S 420 90, 590 20"
            fill="none" stroke="{accent}" stroke-width="10" stroke-linecap="round" stroke-dasharray="800" stroke-dashoffset="800"/></svg>
          <div class="ch-l">{label}</div></div>'''
        js.append(f'tl.to("#{vid} .ch-line", {{strokeDashoffset: 0, duration: 1.0, ease: "power2.out"}}, AT + 0.3);')
    elif t == "chat":
        body = f'''<div class="card chatbox"><div class="cb-q">{label or "What should we build?"}</div>
          <div class="cb-in"><span class="cb-type">{title or value}</span><span class="cb-send">&#10148;</span></div></div>'''
        js.append(f'tl.fromTo("#{vid} .cb-type", {{clipPath: "inset(0 100% 0 0)"}}, {{clipPath: "inset(0 0% 0 0)", duration: 0.9, ease: "none"}}, AT + 0.3);')
        js.append(f'tl.fromTo("#{vid} .cb-send", {{scale: 1}}, {{scale: 1.3, duration: 0.15, repeat: 1, yoyo: true}}, AT + 1.3);')
    elif t == "checklist":
        rows = "".join(f'<div class="ck"><span class="ck-b">&#10003;</span>{x}</div>' for x in items) or f'<div class="ck"><span class="ck-b">&#10003;</span>{value}</div>'
        body = f'<div class="card"><div class="ck-t">{title}</div>{rows}</div>'
        js.append(f'tl.fromTo("#{vid} .ck", {{opacity: 0, x: 40}}, {{opacity: 1, x: 0, duration: 0.25, stagger: 0.35}}, AT + 0.25);')
        js.append(f'tl.fromTo("#{vid} .ck-b", {{scale: 0}}, {{scale: 1, duration: 0.2, stagger: 0.35, ease: "back.out(3)"}}, AT + 0.45);')
    elif t == "calendar":
        body = f'''<div class="cal"><div class="cal-top">{label or "today"}</div><div class="cal-v">{value or "NOW"}</div>
          <div class="cal-s">{title}</div></div>'''
        js.append(f'tl.fromTo("#{vid} .cal", {{rotationX: -90}}, {{rotationX: 0, duration: 0.5, ease: "back.out(1.6)", transformOrigin: "50% 0%"}}, AT);')
    elif t == "cards":
        stack = "".join(f'<div class="stk" style="z-index:{10 - k}"><span class="stk-n">{k + 1:02d}</span>{x}</div>' for k, x in enumerate(items or [value]))
        body = f'<div class="stack"><div class="stk-t">{title}</div>{stack}</div>'
        js.append(f'tl.fromTo("#{vid} .stk", {{y: 200, opacity: 0, rotation: 6}}, {{y: 0, opacity: 1, rotation: 0, duration: 0.35, stagger: 0.25, ease: "back.out(1.6)"}}, AT + 0.2);')
    elif t == "versus":
        left, right = (items + ["", ""])[:2]
        body = f'''<div class="vs"><div class="vs-c bad"><div class="vs-h">&#10007; {label or "before"}</div><div class="vs-b">{left}</div></div>
          <div class="vs-c good"><div class="vs-h">&#10003; {title or "after"}</div><div class="vs-b">{right}</div></div></div>'''
        js.append(f'tl.fromTo("#{vid} .bad", {{x: -400, opacity: 0}}, {{x: 0, opacity: 1, duration: 0.35}}, AT + 0.1);')
        js.append(f'tl.fromTo("#{vid} .good", {{x: 400, opacity: 0}}, {{x: 0, opacity: 1, duration: 0.35}}, AT + 0.7);')
    elif t == "progress":
        pre, n, suf = _num(v.get("value"))
        pct = max(5, min(100, n if n is not None else 70))
        body = f'''<div class="card"><div class="pg-t">{title}</div><div class="pg"><div class="pg-f" style="width:{pct}%"></div></div>
          <div class="pg-v">{value}</div><div class="pg-l">{label}</div></div>'''
        js.append(f'tl.fromTo("#{vid} .pg-f", {{scaleX: 0}}, {{scaleX: 1, duration: 0.9, ease: "power2.out", transformOrigin: "0% 50%"}}, AT + 0.3);')
    elif t == "headline":
        letters = "".join(f'<span class="hl-c">{c if c != " " else "&nbsp;"}</span>' for c in html.unescape(value or title)[:18])
        body = f'<div class="headline"><div class="hl">{letters}</div><div class="hl-u"></div><div class="hl-l">{label}</div></div>'
        js.append(f'tl.fromTo("#{vid} .hl-c", {{opacity: 0, y: 30}}, {{opacity: 1, y: 0, duration: 0.05, stagger: 0.06}}, AT + 0.1);')
        js.append(f'tl.fromTo("#{vid} .hl-u", {{scaleX: 0}}, {{scaleX: 1, duration: 0.4, ease: "power3.out", transformOrigin: "0% 50%"}}, AT + 0.9);')
    else:  # big_text
        body = f'<div class="bigtext"><div class="bt-v">{value or title}</div><div class="bt-l">{label}</div></div>'
        js.append(f'tl.fromTo("#{vid} .bt-v", {{scale: 0.4, opacity: 0}}, {{scale: 1, opacity: 1, duration: 0.35, ease: "back.out(2.4)"}}, AT + 0.1);')
    # Counters count up from 0 (only plain numbers)
    js.append(f'document.querySelectorAll("#{vid} .count").forEach(el => {{ const to = parseFloat(el.dataset.to); '
              f'if (!isNaN(to)) {{ const o = {{n: 0}}; const dec = (String(el.dataset.to).split(".")[1] || "").length; '
              f'tl.to(o, {{n: to, duration: 0.9, ease: "power2.out", onUpdate: () => {{ el.textContent = o.n.toFixed(dec); }}}}, AT + 0.3); }} }});')
    js.insert(0, f'tl.fromTo("#{vid} > *", {{scale: 0.7, opacity: 0, y: 40}}, {{scale: 1, opacity: 1, y: 0, duration: 0.35, ease: "back.out(1.8)"}}, AT);')
    return body, js, 0.0


CONFETTI = 26


def _confetti(at: float) -> list[str]:
    js = []
    for k in range(CONFETTI):
        dx = round(math.cos(k * 2.4) * (180 + (k * 37) % 260), 1)
        dy = round(-260 - (k * 53) % 420, 1)
        js.append(f'tl.fromTo("#cf{k}", {{x: 0, y: 0, opacity: 1, rotation: 0}}, {{x: {dx}, y: {dy}, rotation: {(k * 47) % 360}, '
                  f'opacity: 0, duration: 1.3, ease: "power2.out", immediateRender: false}}, {round(at, 2)});')
    return js


def _gesture(name: str, at: float) -> list[str]:
    arm_r, arm_l = 'svgOrigin: "412 600"', 'svgOrigin: "188 600"'
    poses = {
        "point": [f'tl.to("#armR", {{rotation: -150, duration: 0.3, {arm_r}, ease: "back.out(2)"}}, {at});',
                  f'tl.to("#armL", {{rotation: 0, duration: 0.3, {arm_l}}}, {at});'],
        "explain": [f'tl.to("#armR", {{rotation: -60, duration: 0.3, {arm_r}}}, {at});',
                    f'tl.to("#armL", {{rotation: 50, duration: 0.3, {arm_l}}}, {at});'],
        "shrug": [f'tl.to("#armR", {{rotation: -95, duration: 0.3, {arm_r}}}, {at});',
                  f'tl.to("#armL", {{rotation: 95, duration: 0.3, {arm_l}}}, {at});'],
        "mouth": [f'tl.to("#armL", {{rotation: 165, duration: 0.3, {arm_l}}}, {at});',
                  f'tl.to("#armR", {{rotation: 0, duration: 0.3, {arm_r}}}, {at});'],
        "thumbs": [f'tl.to("#armR", {{rotation: -120, duration: 0.3, {arm_r}, ease: "back.out(2)"}}, {at});',
                   f'tl.to("#armL", {{rotation: 0, duration: 0.3, {arm_l}}}, {at});'],
        "celebrate": [f'tl.to("#armR", {{rotation: -165, duration: 0.3, {arm_r}}}, {at});',
                      f'tl.to("#armL", {{rotation: 165, duration: 0.3, {arm_l}}}, {at});'],
        "think": [f'tl.to("#armR", {{rotation: -135, duration: 0.3, {arm_r}}}, {at});',
                  f'tl.to("#armL", {{rotation: 0, duration: 0.3, {arm_l}}}, {at});'],
    }
    brows = {"mouth": "b-up", "shrug": "b-skeptical", "think": "b-skeptical", "celebrate": "b-up", "thumbs": "b-up"}
    js = poses.get(name, poses["explain"])
    js += [f'tl.set(".brow", {{opacity: 0}}, {at});', f'tl.set("#{brows.get(name, "b-neutral")}", {{opacity: 1}}, {at});']
    return js


def composition(post: dict, account: dict, spans: list[tuple[float, float]], total: float) -> str:
    accent = PAPER_ACCENT.get(account["id"], "#E63946")
    look = {**LOOKS.get(account["id"], LOOKS["acc1"])}
    t_fonts = account["fonts"]
    lines = [post["hook"], *[b["say"] for b in post["beats"]], post["cta"]]
    emph = [[]] + [[b.get("emphasis", "")] for b in post["beats"]] + [[]]
    n_beats = len(post["beats"])

    caps, visuals, js = [], [], []
    for li, (line, (s, e)) in enumerate(zip(lines, spans)):
        parts = chunks(line, size=4)
        total_chars = sum(len(p) for p in parts) or 1
        t = s
        for ci, part in enumerate(parts):
            d = (e - s) * len(part) / total_chars
            cid = f"c{li}_{ci}"
            caps.append(f'<div id="{cid}" class="clip cap" data-start="{round(t, 2)}" data-duration="{round(max(0.25, d), 2)}" '
                        f'data-track-index="2"><div class="cap-t">{_caption_html(part, emph[li] if li else [post["hook"].split()[-1]])}</div></div>')
            # Each word appears as it's spoken (time split by characters within the phrase)
            words, before = part.split(), 0
            for wi, w in enumerate(words):
                wt = round(t + d * before / max(1, len(part)), 2)
                js.append(f'tl.fromTo("#{cid} .cw:nth-child({wi + 1})", {{y: 22, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.1, ease: "power2.out"}}, {wt});')
                before += len(w) + 1
            t += d
        # Mouth moves while speaking
        js += [f'tl.set(".mouth", {{opacity: 0}}, {s});', f'tl.set("#m-talk", {{opacity: 1}}, {s});',
               f'tl.fromTo("#talkshape", {{scaleY: 0.25}}, {{scaleY: 1, duration: 0.11, repeat: {max(1, int((e - s) / 0.11))}, '
               f'yoyo: true, ease: "none", svgOrigin: "300 460"}}, {s});',
               f'tl.set("#m-talk", {{opacity: 0}}, {e});', f'tl.set("#m-happy", {{opacity: 1}}, {e});']

    # Hook beat: a big "??" pops while the presenter reacts; then one illustration per beat
    hs, he = spans[0]
    visuals.append(f'<div id="vhook" class="clip vis" data-start="0" data-duration="{spans[1][0]}" data-track-index="1">'
                   f'<div class="hookmark">??</div></div>')
    js += ['tl.fromTo("#vhook .hookmark", {scale: 0, rotation: -20}, {scale: 1, rotation: -8, duration: 0.4, ease: "back.out(3)"}, 0.15);',
           f'tl.to("#vhook .hookmark", {{rotation: 8, duration: 0.12, repeat: 5, yoyo: true}}, 0.6);']
    cs = spans[-1][0]
    visuals.append(f'<div id="vcta" class="clip vis" data-start="{cs}" data-duration="{round(total - cs, 2)}" data-track-index="1">'
                   f'<div class="ctacard"><div class="cta-save">SAVE THIS</div><div class="cta-f">Follow <b>@{_e(account["handle"])}</b></div></div></div>')
    js += [f'tl.fromTo("#vcta .ctacard", {{y: 300, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.4, ease: "back.out(1.6)"}}, {cs});',
           f'tl.fromTo("#vcta .cta-save", {{scale: 2.2, opacity: 0, rotation: -18}}, {{scale: 1, opacity: 1, rotation: -6, duration: 0.25, ease: "power4.in"}}, {round(cs + 0.4, 2)});']
    js += _gesture("mouth", 0.1) + ['tl.fromTo("#mascot", {y: 600}, {y: 0, duration: 0.5, ease: "back.out(1.6)"}, 0);']
    scenes_html, prev_scene = [], "paper"
    scene_colors = {"paper": PAPER, "ink": INK, "accent": accent}
    for bi, beat in enumerate(post["beats"], 1):
        s, e = spans[bi]
        nxt = spans[bi + 1][0] if bi + 1 < len(spans) else total
        scene = beat.get("scene", "paper") if beat.get("scene") in SCENES else "paper"
        scenes_html.append(f'<div id="sc{bi}" class="clip scene" data-start="{s}" data-duration="{round(nxt - s, 2)}" '
                           f'data-track-index="0" style="background:{scene_colors[scene]}"></div>')
        if scene != prev_scene:  # wipe into the new scene
            js.append(f'tl.fromTo("#sc{bi}", {{clipPath: "inset(0 0 100% 0)"}}, {{clipPath: "inset(0 0 0% 0)", duration: 0.35, ease: "power3.inOut"}}, {s});')
        js.append(f'tl.set("#root", {{attr: {{"data-scene": "{scene}"}}}}, {s});')
        prev_scene = scene
        # Slow camera push-in on the illustration, with a quick glitch as it arrives
        js.append(f'tl.fromTo("#v{bi}", {{scale: 1}}, {{scale: 1.05, duration: {round(nxt - s, 2)}, ease: "none", transformOrigin: "50% 35%"}}, {s});')
        js.append(f'tl.fromTo("#v{bi}", {{x: -18, opacity: 0.6}}, {{x: 0, opacity: 1, duration: 0.12, ease: "steps(3)"}}, {s});')
        if beat.get("gesture") == "celebrate":
            js += _confetti(s + 0.2)
        body, vjs, _ = visual(bi, beat.get("visual") or {}, accent)
        visuals.append(f'<div id="v{bi}" class="clip vis" data-start="{s}" data-duration="{round(nxt - s, 2)}" data-track-index="1">{body}</div>')
        js += [x.replace("AT", str(s)) for x in vjs]
        js += _gesture(beat.get("gesture", "explain"), s)
        js.append(f'tl.set("#meta-r", {{textContent: "BEAT {bi}/{n_beats}"}}, {s});')
        js.append(f'tl.set("#meta-l", {{textContent: "// {bi:02d} · {_e(beat.get("visual", {}).get("type", "idea")).replace("_", " ")}"}}, {s});')
    js += _gesture("celebrate", spans[-1][0]) + _confetti(spans[-1][0] + 0.5)
    scenes_html.append(f'<div id="sccta" class="clip scene" data-start="{spans[-1][0]}" data-duration="{round(total - spans[-1][0], 2)}" '
                       f'data-track-index="0" style="background:{accent}"></div>')
    js.append(f'tl.fromTo("#sccta", {{clipPath: "inset(0 0 100% 0)"}}, {{clipPath: "inset(0 0 0% 0)", duration: 0.35, ease: "power3.inOut"}}, {spans[-1][0]});')
    js.append(f'tl.set("#root", {{attr: {{"data-scene": "accent"}}}}, {spans[-1][0]});')
    js.append(f'tl.set("#meta-l", {{textContent: "// end · save this"}}, {spans[-1][0]});')
    js.append(f'tl.set("#meta-r", {{textContent: "DONE"}}, {spans[-1][0]});')
    js.append(f'tl.to("#grain", {{backgroundPosition: "41px 67px", duration: 0.08, ease: "steps(1)", repeat: {int(total / 0.08)}, yoyo: true}}, 0);')
    js.append('tl.fromTo("#badge", {x: -300}, {x: 0, duration: 0.4, ease: "back.out(1.6)"}, 0.6);')

    fonts = "\n".join(_font_faces({"fonts": {"heading": h, "body": b}})
                      for h, b in (("DM Serif Display", "Inter"), ("JetBrains Mono", account["fonts"]["body"])))
    css = f'''
{fonts}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: {PAPER}; }}
#root {{ width: 1080px; height: 1920px; position: relative; overflow: hidden; background: {PAPER}; color: {INK};
  font-family: '{t_fonts["body"]}', sans-serif; }}
.clip {{ position: absolute; inset: 0; }}
.meta {{ position: absolute; top: 56px; font-family: 'JetBrains Mono', monospace; font-size: 26px; letter-spacing: .04em; opacity: .55; }}
#meta-l {{ left: 60px; }} #meta-r {{ right: 60px; color: {accent}; opacity: .9; }}
.handle {{ position: absolute; top: 56px; left: 0; right: 0; text-align: center; font-family: 'JetBrains Mono', monospace; font-size: 26px; opacity: .45; }}
.cap {{ pointer-events: none; }}
.cap-t {{ position: absolute; top: 150px; left: 60px; right: 60px; font-size: 84px; line-height: 1.08; font-weight: 600;
  letter-spacing: -0.02em; font-family: 'Inter', sans-serif; }}
.em {{ color: {accent}; font-family: 'DM Serif Display', serif; font-style: italic; font-weight: 400; }}
#stage {{ position: absolute; right: -40px; bottom: -150px; transform: scale(.82); transform-origin: bottom right; }}
.vis {{ display: flex; align-items: flex-start; justify-content: center; padding-top: 450px; }}
.vis > * {{ max-width: 900px; transform-origin: 50% 0%; }}
.vis .card, .vis .stack, .vis .cal {{ zoom: 1.12; }}
.vis .vs {{ zoom: 1.05; width: 880px; }}
.card {{ background: #fff; border: 5px solid {INK}; border-radius: 30px; padding: 40px 46px; box-shadow: 10px 10px 0 {INK}; width: 760px; }}
.phone {{ width: 430px; height: 760px; background: {INK}; border-radius: 60px; padding: 70px 34px 34px; position: relative; color: #fff; box-shadow: 12px 12px 0 {accent}; }}
.notch {{ position: absolute; top: 22px; left: 50%; margin-left: -70px; width: 140px; height: 30px; background: #000; border-radius: 20px; }}
.ph-head {{ display: flex; gap: 20px; align-items: center; }} .ph-av {{ width: 80px; height: 80px; border-radius: 50%; background: {accent}; }}
.ph-name {{ font-size: 32px; font-weight: 700; }} .ph-sub {{ font-size: 24px; opacity: .6; }}
.ph-big {{ font-size: 120px; font-weight: 800; margin: 60px 0 30px; color: #fff; }}
.ph-bars {{ display: flex; gap: 14px; align-items: flex-end; height: 140px; }} .ph-bar {{ flex: 1; background: {accent}; border-radius: 8px; }}
.doc-t {{ font-size: 46px; font-weight: 800; margin-bottom: 26px; }} .doc-l {{ height: 22px; background: #E4E1DA; border-radius: 10px; margin: 16px 0; font-size: 30px; }}
.doc-l:not(:empty) {{ height: auto; background: none; color: #555; }} .doc-l.short {{ width: 60%; }}
.doc {{ position: relative; min-height: 380px; }}
.stampmark {{ position: absolute; right: 30px; bottom: 40px; border: 8px solid {accent}; color: {accent}; font-weight: 900;
  font-size: 72px; padding: 6px 26px; border-radius: 14px; letter-spacing: .06em; text-transform: uppercase; opacity: 0; }}
.counterbox {{ text-align: center; }} .ctr-l {{ font-size: 38px; font-weight: 700; }}
.ctr {{ font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 170px; color: {accent}; margin: 20px 0; }}
.ctr-s, .ch-l, .pg-l, .bt-l {{ font-size: 32px; color: #555; }}
.ch-t, .pg-t, .ck-t, .stk-t {{ font-size: 40px; font-weight: 800; margin-bottom: 12px; }} .ch-v {{ font-size: 96px; font-weight: 800; color: {accent}; }}
.ch-svg {{ width: 100%; height: 240px; }}
.cb-q {{ font-size: 40px; text-align: center; margin-bottom: 34px; color: #555; }}
.cb-in {{ display: flex; align-items: center; gap: 20px; border: 4px solid {INK}; border-radius: 26px; padding: 26px 30px; font-size: 40px; }}
.cb-type {{ flex: 1; font-weight: 600; }} .cb-send {{ background: {accent}; color: #fff; width: 76px; height: 76px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; font-size: 38px; }}
.ck {{ display: flex; gap: 22px; align-items: center; font-size: 40px; margin: 22px 0; font-weight: 600; }}
.ck-b {{ width: 58px; height: 58px; border-radius: 14px; background: {accent}; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 36px; flex: none; }}
.cal {{ width: 520px; background: #fff; border: 5px solid {INK}; border-radius: 30px; text-align: center; overflow: hidden; box-shadow: 10px 10px 0 {INK}; }}
.cal-top {{ background: {accent}; color: #fff; font-size: 36px; font-weight: 800; padding: 18px; text-transform: uppercase; letter-spacing: .1em; }}
.cal-v {{ font-size: 150px; font-weight: 900; padding: 30px 0 10px; }} .cal-s {{ font-size: 32px; color: #555; padding-bottom: 30px; }}
.stack {{ width: 780px; }} .stk {{ background: #fff; border: 5px solid {INK}; border-radius: 26px; padding: 30px 36px; font-size: 40px; font-weight: 600;
  margin-bottom: 20px; box-shadow: 8px 8px 0 {INK}; display: flex; gap: 22px; }} .stk-n {{ color: {accent}; font-family: 'JetBrains Mono', monospace; font-weight: 700; }}
.vs {{ display: flex; gap: 30px; width: 900px; }} .vs-c {{ flex: 1; background: #fff; border: 5px solid {INK}; border-radius: 28px; padding: 34px; box-shadow: 8px 8px 0 {INK}; }}
.vs-h {{ font-size: 40px; font-weight: 800; margin-bottom: 18px; }} .bad .vs-h {{ color: #999; }} .good .vs-h {{ color: {accent}; }} .vs-b {{ font-size: 36px; line-height: 1.3; }}
.pg {{ height: 56px; background: #E4E1DA; border-radius: 30px; overflow: hidden; margin: 26px 0; }} .pg-f {{ height: 100%; background: {accent}; }}
.pg-v {{ font-size: 90px; font-weight: 900; color: {accent}; }}
.bigtext {{ text-align: center; }} .bt-v {{ font-size: 170px; font-weight: 900; line-height: 1; color: {INK}; }}
.brow, .mouth, #burst {{ opacity: 0; }} #b-up, #m-happy {{ opacity: 1; }}
.scene {{ z-index: 0; }} #world {{ z-index: 1; }} .vis {{ z-index: 2; }} .cap {{ z-index: 3; }}
#root[data-scene="ink"] .cap-t, #root[data-scene="ink"] .meta, #root[data-scene="ink"] .handle,
#root[data-scene="accent"] .cap-t, #root[data-scene="accent"] .meta, #root[data-scene="accent"] .handle {{ color: #fff; }}
#root[data-scene="accent"] .em {{ color: {INK}; }} #root[data-scene="ink"] .bt-v, #root[data-scene="ink"] .hl {{ color: #fff; }}
#grain {{ position: absolute; inset: -60px; pointer-events: none; opacity: .14; mix-blend-mode: multiply; z-index: 9;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='160' height='160' filter='url(%23n)'/></svg>"); }}
#badge {{ position: absolute; left: 50px; bottom: 60px; display: flex; gap: 16px; align-items: center; background: #fff; border: 4px solid {INK};
  border-radius: 20px; padding: 14px 20px; box-shadow: 6px 6px 0 {accent}; z-index: 4; }}
.bd-m {{ width: 56px; height: 56px; border-radius: 14px; background: {accent}; color: #fff; font-weight: 900; font-size: 34px;
  display: flex; align-items: center; justify-content: center; }}
.bd-t {{ font-family: 'JetBrains Mono', monospace; font-size: 22px; font-weight: 700; line-height: 1.3; color: {INK}; }} .bd-t span {{ opacity: .55; font-weight: 400; }}
#confetti {{ position: absolute; right: 320px; bottom: 700px; z-index: 5; }} .cf {{ position: absolute; width: 18px; height: 26px; border-radius: 4px; opacity: 0; }}
.cw {{ display: inline-block; }}
.headline {{ text-align: center; }} .hl {{ font-size: 150px; font-weight: 900; letter-spacing: -0.02em; line-height: 1; color: {INK}; }}
.hl-c {{ display: inline-block; }} .hl-u {{ height: 18px; background: {accent}; margin: 18px auto 0; width: 80%; border-radius: 10px; }}
.hl-l {{ font-size: 36px; color: #777; margin-top: 22px; }}
.hookmark {{ font-family: 'DM Serif Display', serif; font-style: italic; font-size: 420px; line-height: 1; color: {accent}; margin-top: 40px; }}
.ctacard {{ background: {INK}; color: #fff; border-radius: 34px; padding: 60px 70px; text-align: center; box-shadow: 12px 12px 0 {accent}; margin-top: 60px; }}
.cta-save {{ display: inline-block; border: 8px solid {accent}; color: {accent}; font-weight: 900; font-size: 96px; padding: 8px 30px;
  border-radius: 16px; letter-spacing: .06em; }}
.cta-f {{ margin-top: 36px; font-size: 46px; }} .cta-f b {{ color: {accent}; }}
'''
    body = f'''<div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1080" data-height="1920">
  {"".join(scenes_html)}
  <div id="world" class="clip" data-start="0" data-duration="{total}" data-track-index="0">
    <div id="meta-l" class="meta">// 00 · hook</div><div class="handle">@{_e(account["handle"])}</div>
    <div id="meta-r" class="meta">BEAT 0/{n_beats}</div>
    <div id="stage">{character(look)}</div>
    <div id="badge"><div class="bd-m">{_e(account["handle"][:1].upper())}</div><div class="bd-t">@{_e(account["handle"])}<br><span>founder notes</span></div></div>
    <div id="confetti">{"".join(f'<i id="cf{k}" class="cf" style="background:{[accent, INK, "#FFD60A", "#fff"][k % 4]}"></i>' for k in range(CONFETTI))}</div>
    <div id="grain"></div></div>
  {"".join(visuals)}{"".join(caps)}
  <audio id="vo" data-start="0" data-duration="{total}" data-track-index="8" data-volume="1" src="assets/voice.wav"></audio>
  <audio id="music" data-start="0" data-duration="{total}" data-track-index="9" data-volume="0.12" src="assets/music.mp3"></audio>
</div>'''
    return f'''<!doctype html>
<html lang="en" data-resolution="portrait"><head><meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="assets/gsap.min.js"></script><style>{css}</style></head><body>
{body}
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
window.__timelines["main"] = tl;
tl.seek(0);
</script></body></html>'''


def render(post: dict, account: dict, music: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out.parent / "voice.wav"
    lines = [post["hook"], *[b["say"] for b in post["beats"]], post["cta"]]
    spans = voice.narrate(lines, account["id"], wav)
    total = round(spans[-1][1] + 0.6, 2)
    page = composition(post, account, spans, total)
    return render_project(page, music, out, extra={"voice.wav": wav})
