"""2D animated Reel formats rendered with HyperFrames (HTML + SVG + GSAP -> MP4):

- chat:       an animated DM conversation (You <-> an investor/mentor/customer), typing dots, bubbles popping in
- myth_fact:  a MYTH card gets a red X stamp, then the FACT slides in with a green tick; the mascot reacts
- checklist:  a clipboard where each item gets ticked off while the mascot points along
"""
import html
import math
from pathlib import Path

from engine.render.animated import _font_faces, _read_time, _size, _words, render_project
from engine.render.carousel import _theme
from engine.render.mascot import FACES, LOOKS, character

FORMATS = ("chat", "myth_fact", "checklist")


def _esc(text: str) -> str:
    return html.escape(text.strip())


def _head(account: dict, extra_css: str) -> str:
    t = _theme(account)
    return f'''<!doctype html>
<html lang="en" data-resolution="portrait"><head><meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="assets/gsap.min.js"></script>
<style>
{_font_faces(account)}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
#root {{ width: 1080px; height: 1920px; position: relative; overflow: hidden; background: {t["bg"]};
  color: {t["text"]}; font-family: '{t["body"]}', sans-serif; }}
.heading {{ font-family: '{t["heading"]}', sans-serif; font-weight: 800; line-height: 1.12; }}
.w {{ display: inline-block; }}
.hot {{ color: {t["accent"]}; }}
.clip {{ position: absolute; inset: 0; }}
.handle {{ position: absolute; bottom: 70px; width: 100%; text-align: center; font-size: 32px; font-weight: 600; opacity: .75; }}
.cta {{ position: absolute; left: 60px; right: 60px; bottom: 150px; background: {t["accent"]}; color: {t["on_accent"]};
  border-radius: 40px; padding: 40px; text-align: center; }}
.cta .line {{ font-size: 54px; }}
.cta .follow {{ margin-top: 16px; font-size: 40px; font-weight: 600; }}
.brow, .mouth, #burst {{ opacity: 0; }}
{extra_css}
</style></head><body>'''


def _tail(total: float, js: list[str]) -> str:
    return f'''<audio id="music" data-start="0" data-duration="{total}" data-track-index="9" data-volume="0.8" src="assets/music.mp3"></audio>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
window.__timelines["main"] = tl;
tl.seek(0);
</script></body></html>'''


def _root(total: float) -> str:
    return (f'<div id="root" data-composition-id="main" data-start="0" data-duration="{total}" '
            f'data-width="1080" data-height="1920">')


def _cta(post: dict, account: dict, start: float, total: float) -> tuple[str, list[str]]:
    el = f'''<div id="ctaclip" class="clip" data-start="{start}" data-duration="{round(total - start, 2)}" data-track-index="5">
      <div class="cta"><div class="line heading">{_esc(post["cta"])}</div>
      <div class="follow">Follow @{_esc(account["handle"])}</div></div></div>'''
    js = [f'tl.fromTo("#ctaclip .cta", {{y: 300, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.4, ease: "back.out(1.6)"}}, {start});']
    return el, js


def _face_css(name: str) -> str:
    brow, mouth = FACES[name]
    return f"#{brow}, #{mouth} {{ opacity: 1; }}"


def _face(name: str, at: float) -> list[str]:
    brow, mouth = FACES[name]
    return [f'tl.set(".brow, .mouth", {{opacity: 0}}, {at});', f'tl.set("#{brow}, #{mouth}", {{opacity: 1}}, {at});']


# ---------- chat ----------

def chat(post: dict, account: dict) -> tuple[str, float]:
    t = _theme(account)
    msgs = post["messages"]
    hook_t = _read_time(post["hook"], 2.0, 3.0)
    # Layout: estimate wrapped lines to stack bubbles; scroll the thread up once it overflows
    view_h, y, gap = 1080, 0, 24
    timeline, cursor = [], hook_t
    for m in msgs:
        lines = max(1, math.ceil(len(m["text"]) / 28))
        h = 52 + lines * 54
        typing = 0.7 if m["side"] == "them" else 0.25
        hold = _read_time(m["text"], 1.2, 3.2, extra=0.0)
        timeline.append({"y": y, "h": h, "typing_at": round(cursor, 2), "show_at": round(cursor + typing, 2),
                         "scroll": max(0, y + h - view_h)})
        y += h + gap
        cursor += typing + hold
    cta_at = round(cursor, 2)
    total = round(cta_at + _read_time(post["cta"], 2.6, 4.0, extra=0.9), 2)

    bubbles = []
    for i, (m, l) in enumerate(zip(msgs, timeline)):
        side = "you" if m["side"] == "you" else "them"
        bubbles.append(f'<div id="m{i}" class="msg {side}" style="top:{l["y"]}px">{_esc(m["text"])}</div>')
    css = f'''
#hook {{ position: absolute; top: 120px; left: 70px; right: 70px; text-align: center; }}
#card {{ position: absolute; top: 440px; left: 50px; right: 50px; height: 1300px; background: #fff; border-radius: 48px;
  overflow: hidden; box-shadow: 0 24px 60px rgba(0,0,0,.25); }}
#bar {{ height: 130px; display: flex; align-items: center; gap: 24px; padding: 0 40px; border-bottom: 2px solid #eee; color: #111; }}
#avatar {{ width: 76px; height: 76px; border-radius: 50%; background: {t["accent"]}; color: {t["on_accent"]};
  display: flex; align-items: center; justify-content: center; font-size: 38px; font-weight: 800; }}
#who {{ font-size: 40px; font-weight: 700; }} #status {{ font-size: 28px; color: #2BB673; }}
#viewport {{ position: absolute; top: 132px; left: 0; right: 0; bottom: 0; overflow: hidden; }}
#thread {{ position: absolute; top: 28px; left: 36px; right: 36px; }}
.msg {{ position: absolute; max-width: 700px; padding: 26px 34px; border-radius: 36px; font-size: 42px; line-height: 1.28; opacity: 0; }}
.them {{ left: 0; background: #EFEFF3; color: #111; border-bottom-left-radius: 10px; }}
.you {{ right: 0; background: {t["accent"]}; color: {t["on_accent"]}; border-bottom-right-radius: 10px; }}
#typing {{ position: absolute; left: 36px; padding: 26px 34px; background: #EFEFF3; border-radius: 36px; opacity: 0; display: flex; gap: 12px; }}
#typing span {{ width: 18px; height: 18px; border-radius: 50%; background: #999; display: inline-block; }}
'''
    role = _esc(post.get("other_role", "Mentor"))[:20]
    body = f'''{_root(total)}
  <div id="scene" class="clip" data-start="0" data-duration="{total}" data-track-index="0">
    <div id="hook" class="heading" style="font-size:{_size(post["hook"], 84, 72, 62)}px">{_words(post["hook"], "w")}</div>
    <div id="card"><div id="bar"><div id="avatar">{role[:1].upper()}</div>
      <div><div id="who">{role}</div><div id="status">online</div></div></div>
      <div id="viewport"><div id="thread">{"".join(bubbles)}<div id="typing"><span></span><span></span><span></span></div></div></div></div>
    <div class="handle">@{_esc(account["handle"])}</div></div>'''
    js = ['tl.fromTo("#hook .w", {y: 60, opacity: 0}, {y: 0, opacity: 1, duration: 0.3, stagger: 0.06, ease: "back.out(2)"}, 0);',
          'tl.fromTo("#card", {y: 900}, {y: 0, duration: 0.5, ease: "power3.out"}, 0.6);']
    for i, (m, l) in enumerate(zip(msgs, timeline)):
        if l["scroll"]:
            js.append(f'tl.to("#thread", {{y: -{l["scroll"]}, duration: 0.3, ease: "power2.out"}}, {l["typing_at"]});')
        if m["side"] == "them":
            js += [f'tl.set("#typing", {{top: {l["y"]}, opacity: 1}}, {l["typing_at"]});',
                   f'tl.fromTo("#typing span", {{y: 0}}, {{y: -12, duration: 0.15, stagger: 0.08, repeat: 1, yoyo: true}}, {l["typing_at"]});',
                   f'tl.set("#typing", {{opacity: 0}}, {l["show_at"]});']
        js.append(f'tl.fromTo("#m{i}", {{opacity: 0, scale: 0.6, y: 30}}, {{opacity: 1, scale: 1, y: 0, duration: 0.28, '
                  f'ease: "back.out(2)", transformOrigin: "{"100%" if m["side"] == "you" else "0%"} 100%"}}, {l["show_at"]});')
    # Lift the chat when the follow card arrives so the last (key) message stays readable
    js += [f'tl.to("#hook", {{opacity: 0, duration: 0.25}}, {cta_at});',
           f'tl.to("#card", {{y: -330, duration: 0.4, ease: "power2.inOut"}}, {cta_at});']
    cta_el, cta_js = _cta(post, account, cta_at, total)
    return _head(account, css) + body + cta_el + _tail(total, js + cta_js), total


# ---------- myth vs fact ----------

def myth_fact(post: dict, account: dict) -> tuple[str, float]:
    look = LOOKS.get(account["id"], LOOKS["acc1"])
    hook_t = _read_time(post["hook"], 2.2, 3.2)
    scenes, js, cursor = [], [], hook_t
    js += ['tl.fromTo("#hook .w", {y: 70, opacity: 0, scale: 0.6}, {y: 0, opacity: 1, scale: 1, duration: 0.32, stagger: 0.06, '
           'ease: "back.out(2.2)"}, 0);',
           f'tl.to("#hook", {{opacity: 0, y: -60, duration: 0.25}}, {round(hook_t - 0.25, 2)});',
           'tl.fromTo("#mascot", {y: 500}, {y: 0, duration: 0.45, ease: "back.out(1.8)"}, 0);',
           f'tl.to("#body", {{y: -10, duration: 0.9, repeat: 40, yoyo: true, ease: "sine.inOut"}}, 0);']
    for i, p in enumerate(post["pairs"]):
        myth_t = _read_time(p["myth"], 1.8, 3.4)
        fact_t = _read_time(p["fact"], 2.2, 4.4)
        s, stamp, fact_at = round(cursor, 2), round(cursor + myth_t, 2), round(cursor + myth_t + 0.6, 2)
        dur = round(myth_t + 0.6 + fact_t, 2)
        scenes.append(f'''<div id="p{i}" class="clip" data-start="{s}" data-duration="{dur}" data-track-index="1">
      <div class="card myth"><div class="tag red">MYTH</div>
        <div class="txt" style="font-size:{_size(p["myth"], 76, 66, 58)}px">{_esc(p["myth"])}</div>
        <div class="stamp">&#10005;</div></div>
      <div class="card fact"><div class="tag green">FACT</div>
        <div class="txt" style="font-size:{_size(p["fact"], 70, 62, 54)}px">{_esc(p["fact"])}</div>
        <div class="tick">&#10003;</div></div></div>''')
        js += [f'tl.fromTo("#p{i} .myth", {{x: -900}}, {{x: 0, duration: 0.4, ease: "power3.out"}}, {s});',
               *_face("skeptical", s),
               f'tl.fromTo("#head", {{rotation: -5}}, {{rotation: 5, duration: 0.18, repeat: 5, yoyo: true, svgOrigin: "300 500"}}, {s + 0.3});',
               f'tl.fromTo("#p{i} .stamp", {{scale: 3, opacity: 0, rotation: -30}}, {{scale: 1, opacity: 1, rotation: -12, duration: 0.25, '
               f'ease: "power4.in"}}, {stamp});',
               f'tl.to("#p{i} .myth", {{x: 12, duration: 0.05, repeat: 3, yoyo: true}}, {round(stamp + 0.25, 2)});',
               f'tl.to("#p{i} .myth", {{opacity: 0.35, scale: 0.92, y: -40, duration: 0.3}}, {round(fact_at - 0.1, 2)});',
               f'tl.fromTo("#p{i} .fact", {{y: 500, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.4, ease: "back.out(1.4)"}}, {fact_at});',
               f'tl.fromTo("#p{i} .tick", {{scale: 0}}, {{scale: 1, duration: 0.3, ease: "back.out(3)"}}, {round(fact_at + 0.35, 2)});',
               *_face("happy", fact_at),
               f'tl.fromTo("#head", {{rotation: 0}}, {{rotation: 6, duration: 0.2, repeat: 3, yoyo: true, svgOrigin: "300 500"}}, {fact_at + 0.1});']
        cursor += dur
    cta_at = round(cursor, 2)
    total = round(cta_at + _read_time(post["cta"], 2.6, 4.0, extra=0.9), 2)
    js += _face("excited", cta_at)
    css = f'''
#hook {{ position: absolute; top: 300px; left: 70px; right: 70px; text-align: center; }}
.card {{ position: absolute; left: 60px; right: 60px; border-radius: 44px; padding: 44px 50px 50px; background: #fff; color: #111;
  box-shadow: 0 18px 50px rgba(0,0,0,.25); }}
.myth {{ top: 170px; }} .fact {{ top: 700px; }}
.tag {{ display: inline-block; font-weight: 800; font-size: 38px; letter-spacing: .08em; padding: 8px 26px; border-radius: 12px; color: #fff; margin-bottom: 22px; }}
.red {{ background: #E5383B; }} .green {{ background: #2BB673; }}
.txt {{ font-weight: 600; line-height: 1.25; }}
.stamp {{ position: absolute; left: 0; right: 0; top: 50%; margin-top: -170px; text-align: center; font-size: 300px;
  line-height: 340px; font-weight: 900; color: #E5383B; opacity: 0; text-shadow: 0 8px 30px rgba(0,0,0,.25); }}
.tick {{ position: absolute; right: 50px; top: 24px; font-size: 110px; font-weight: 900; color: #2BB673; }}
#stage {{ position: absolute; left: 160px; bottom: -230px; }}
{_face_css("happy")}
'''
    body = f'''{_root(total)}
  <div id="scene" class="clip" data-start="0" data-duration="{total}" data-track-index="0">
    <div id="stage">{character(look)}</div><div class="handle">@{_esc(account["handle"])}</div>
    <div id="hook" class="heading" style="font-size:{_size(post["hook"], 104, 88, 74)}px">{_words(post["hook"], "w")}</div></div>
  {"".join(scenes)}'''
    cta_el, cta_js = _cta(post, account, cta_at, total)
    return _head(account, css) + body + cta_el + _tail(total, js + cta_js), total


# ---------- checklist ----------

def checklist(post: dict, account: dict) -> tuple[str, float]:
    t = _theme(account)
    look = LOOKS.get(account["id"], LOOKS["acc1"])
    items = post["items"]
    start = _read_time(post["hook"], 2.0, 3.0)
    rows, js, cursor, y = [], [], start, 0
    js += ['tl.fromTo("#board", {y: 1200, rotation: 4}, {y: 0, rotation: 0, duration: 0.5, ease: "back.out(1.2)"}, 0);',
           'tl.fromTo("#title .w", {y: 40, opacity: 0}, {y: 0, opacity: 1, duration: 0.28, stagger: 0.05, ease: "back.out(2)"}, 0.4);',
           'tl.fromTo("#mascot", {y: 500}, {y: 0, duration: 0.45, ease: "back.out(1.8)"}, 0.3);',
           f'tl.to("#body", {{y: -10, duration: 0.9, repeat: 40, yoyo: true, ease: "sine.inOut"}}, 0);',
           'tl.to("#armR", {rotation: -150, duration: 0.3, svgOrigin: "412 600"}, 0.8);']
    for i, item in enumerate(items):
        lines = max(1, math.ceil(len(item) / 30))
        h = 40 + lines * 56
        rows.append(f'''<div class="row" id="r{i}" style="top:{y}px"><svg class="box" viewBox="0 0 70 70" width="70" height="70">
          <rect x="4" y="4" width="62" height="62" rx="14" fill="none" stroke="#111" stroke-width="6"/>
          <path class="check" d="M16 37 L30 51 L56 20" fill="none" stroke="{'#2BB673'}" stroke-width="9" stroke-linecap="round"
            stroke-linejoin="round" stroke-dasharray="70" stroke-dashoffset="70"/></svg>
          <div class="item">{_esc(item)}</div></div>''')
        hold = _read_time(item, 1.4, 3.4, extra=0.3)
        at = round(cursor, 2)
        js += [f'tl.fromTo("#r{i}", {{opacity: 0, x: 60}}, {{opacity: 1, x: 0, duration: 0.3, ease: "power3.out"}}, {at});',
               f'tl.to("#r{i} .check", {{strokeDashoffset: 0, duration: 0.35, ease: "power2.out"}}, {round(at + 0.4, 2)});',
               f'tl.fromTo("#r{i} .box", {{scale: 1}}, {{scale: 1.2, duration: 0.12, repeat: 1, yoyo: true, transformOrigin: "50% 50%"}}, {round(at + 0.4, 2)});',
               *_face(["happy", "excited", "thinking"][i % 3], at)]
        y += h + 22
        cursor += hold
    cta_at = round(cursor, 2)
    total = round(cta_at + _read_time(post["cta"], 2.6, 4.0, extra=0.9), 2)
    js += _face("excited", cta_at)
    css = f'''
#board {{ position: absolute; top: 120px; left: 60px; right: 60px; background: #fff; color: #111; border-radius: 40px;
  padding: 120px 56px 40px; box-shadow: 0 24px 60px rgba(0,0,0,.25); }}
#clip-top {{ position: absolute; top: -34px; left: 50%; margin-left: -130px; width: 260px; height: 90px; border-radius: 24px;
  background: {t["accent"]}; }}
#title {{ font-size: {_size(post["hook"], 68, 58, 50)}px; text-align: center; margin-bottom: 40px; }}
#list {{ position: relative; }}
.row {{ position: absolute; left: 0; right: 0; display: flex; gap: 28px; align-items: flex-start; opacity: 0; }}
.item {{ font-size: 44px; line-height: 1.27; font-weight: 600; padding-top: 6px; }}
#stage {{ position: absolute; right: -60px; bottom: -260px; transform: scale(.72); transform-origin: bottom right; }}
{_face_css("happy")}
'''
    body = f'''{_root(total)}
  <div id="scene" class="clip" data-start="0" data-duration="{total}" data-track-index="0">
    <div id="stage">{character(look)}</div>
    <div id="board"><div id="clip-top"></div><div id="title" class="heading">{_words(post["hook"], "w")}</div>
      <div id="list" style="height:{y}px">{"".join(rows)}</div></div>
    <div class="handle">@{_esc(account["handle"])}</div></div>'''
    cta_el, cta_js = _cta(post, account, cta_at, total)
    return _head(account, css) + body + cta_el + _tail(total, js + cta_js), total


BUILDERS = {"chat": chat, "myth_fact": myth_fact, "checklist": checklist}


def render(fmt: str, post: dict, account: dict, music: Path, out: Path) -> Path:
    page, _ = BUILDERS[fmt](post, account)
    return render_project(page, music, out)
