"""Mascot Reel: a flat 2D character per account says the hook in a speech bubble with a matching expression,
points at each tip, then waves. Rendered with HyperFrames (HTML + SVG + GSAP -> MP4).

Uses the same script data as reaction Reels: hook, points, cta, reaction (the expression), music_mood.
"""
import html
from pathlib import Path

from engine.render.animated import _font_faces, _read_time, _size, render_project
from engine.render.carousel import _theme

# One look per account: skin, hair, hoodie and an accessory, so every page has its own character
LOOKS = {
    "acc1": {"skin": "#F1C9A5", "hair": "#1A1A1A", "hoodie": "#FFD60A", "trim": "#0A0A0A", "extra": "beanie"},
    "acc2": {"skin": "#C68E68", "hair": "#3B2416", "hoodie": "#1F3A2E", "trim": "#C8763A", "extra": "none"},
    "acc3": {"skin": "#E8B48F", "hair": "#2A2A2A", "hoodie": "#4CC9F0", "trim": "#0B1F3A", "extra": "glasses"},
    "acc4": {"skin": "#A8704C", "hair": "#111111", "hoodie": "#00F5D4", "trim": "#7B2FF7", "extra": "cap"},
    "acc5": {"skin": "#F3D2B8", "hair": "#7A3B1E", "hoodie": "#E63946", "trim": "#1A1A1A", "extra": "none"},
}
POINT_FACES = ["happy", "thinking", "excited"]


def character(look: dict) -> str:
    """SVG character, viewBox 600x900. Parts have ids so the timeline can move them."""
    s, h, c, t = look["skin"], look["hair"], look["hoodie"], look["trim"]
    extra = {
        "glasses": f'<g stroke="{t}" stroke-width="9" fill="none"><rect x="196" y="332" width="92" height="76" rx="22"/>'
                   f'<rect x="312" y="332" width="92" height="76" rx="22"/><line x1="288" y1="366" x2="312" y2="366"/></g>',
        "cap": f'<path d="M142 268 Q150 136 300 136 Q450 136 458 268 Z" fill="{t}"/>'
               f'<path d="M300 258 Q430 246 520 278 Q430 296 300 282 Z" fill="{t}"/>',
        "beanie": f'<path d="M138 268 Q142 128 300 126 Q458 128 462 268 Z" fill="{t}"/>'
                  f'<rect x="130" y="240" width="340" height="40" rx="20" fill="{c}"/>',
        "none": "",
    }[look["extra"]]
    return f'''<svg id="mascot" viewBox="0 0 600 900" width="760" height="1140" xmlns="http://www.w3.org/2000/svg">
  <g id="body">
    <g id="armL"><rect x="150" y="575" width="76" height="250" rx="38" fill="{c}"/><circle cx="188" cy="830" r="40" fill="{s}"/></g>
    <g id="armR"><rect x="374" y="575" width="76" height="250" rx="38" fill="{c}"/><circle cx="412" cy="830" r="40" fill="{s}"/></g>
    <rect x="150" y="540" width="300" height="420" rx="140" fill="{c}"/>
    <path d="M250 545 L300 610 L350 545" stroke="{t}" stroke-width="14" fill="none" stroke-linecap="round"/>
    <rect x="270" y="495" width="60" height="70" rx="20" fill="{s}"/>
    <g id="head">
      <circle cx="132" cy="380" r="30" fill="{s}"/><circle cx="468" cy="380" r="30" fill="{s}"/>
      <circle cx="300" cy="360" r="168" fill="{s}"/>
      <path d="M134 352 Q136 168 300 164 Q464 168 466 352 Q446 250 300 246 Q154 250 134 352 Z" fill="{h}"/>
      <circle cx="215" cy="440" r="24" fill="{t}" opacity=".18"/><circle cx="385" cy="440" r="24" fill="{t}" opacity=".18"/>
      <g id="eyes">
        <g id="eyeL"><ellipse cx="242" cy="370" rx="30" ry="36" fill="#fff"/><circle cx="246" cy="374" r="16" fill="#1A1A1A"/><circle cx="252" cy="366" r="5" fill="#fff"/></g>
        <g id="eyeR"><ellipse cx="358" cy="370" rx="30" ry="36" fill="#fff"/><circle cx="354" cy="374" r="16" fill="#1A1A1A"/><circle cx="360" cy="366" r="5" fill="#fff"/></g>
      </g>
      <g class="brow" id="b-neutral" stroke="{h}" stroke-width="12" stroke-linecap="round"><line x1="214" y1="318" x2="268" y2="314"/><line x1="332" y1="314" x2="386" y2="318"/></g>
      <g class="brow" id="b-up" stroke="{h}" stroke-width="12" stroke-linecap="round" fill="none"><path d="M212 300 Q240 280 270 296"/><path d="M330 296 Q360 280 388 300"/></g>
      <g class="brow" id="b-skeptical" stroke="{h}" stroke-width="12" stroke-linecap="round"><line x1="212" y1="300" x2="268" y2="290"/><line x1="332" y1="322" x2="388" y2="312"/></g>
      <g class="mouth" id="m-happy"><path d="M250 450 Q300 492 350 450" stroke="#1A1A1A" stroke-width="12" fill="none" stroke-linecap="round"/></g>
      <g class="mouth" id="m-excited"><path d="M238 440 Q300 520 362 440 Z" fill="#1A1A1A"/><path d="M256 446 L344 446 L336 462 L264 462 Z" fill="#fff"/></g>
      <g class="mouth" id="m-shocked"><ellipse cx="300" cy="462" rx="34" ry="44" fill="#1A1A1A"/><ellipse cx="300" cy="486" rx="20" ry="12" fill="#E8667A"/></g>
      <g class="mouth" id="m-skeptical"><path d="M258 462 Q300 448 346 470" stroke="#1A1A1A" stroke-width="12" fill="none" stroke-linecap="round"/></g>
      <g class="mouth" id="m-thinking"><circle cx="318" cy="462" r="13" fill="#1A1A1A"/></g>
      <g class="mouth" id="m-talk"><ellipse id="talkshape" cx="300" cy="460" rx="30" ry="18" fill="#1A1A1A"/></g>
      {extra}
      <g id="burst" stroke="#FFFFFF" stroke-width="14" stroke-linecap="round"><line x1="104" y1="176" x2="58" y2="124"/><line x1="300" y1="112" x2="300" y2="46"/><line x1="496" y1="176" x2="542" y2="124"/></g>
    </g>
  </g>
</svg>'''


FACES = {  # expression -> (brows, mouth)
    "shocked": ("b-up", "m-shocked"), "excited": ("b-up", "m-excited"), "skeptical": ("b-skeptical", "m-skeptical"),
    "happy": ("b-neutral", "m-happy"), "thinking": ("b-skeptical", "m-thinking"),
}


def _face(name: str, at: float) -> list[str]:
    brow, mouth = FACES.get(name, FACES["happy"])
    return [f'tl.set(".brow, .mouth", {{opacity: 0}}, {at});', f'tl.set("#{brow}, #{mouth}", {{opacity: 1}}, {at});']


def durations(post: dict) -> list[float]:
    hook = _read_time(post["hook"], 2.6, 3.8)
    points = [_read_time(p["text"], 2.0, 5.0) for p in post["points"]]
    return [hook, *points, _read_time(post["cta"], 2.6, 4.2, extra=0.9)]


def composition(post: dict, account: dict, secs: list[float]) -> str:
    t = _theme(account)
    look = LOOKS.get(account["id"], LOOKS["acc1"])
    total = round(sum(secs), 2)
    starts = [round(sum(secs[:i]), 2) for i in range(len(secs))]
    n = len(post["points"])
    c = len(secs) - 1

    bubbles = [f'''<div id="s0" class="clip scene" data-start="0" data-duration="{secs[0]}" data-track-index="1">
      <div class="bubble"><div class="say heading" style="font-size:{_size(post["hook"], 92, 78, 66)}px">{html.escape(post["hook"])}</div></div></div>''']
    for i, p in enumerate(post["points"], 1):
        bubbles.append(f'''<div id="s{i}" class="clip scene" data-start="{starts[i]}" data-duration="{secs[i]}" data-track-index="1">
      <div class="bubble"><div class="pill">{i}/{n}</div>
      <div class="say" style="font-size:{_size(p["text"], 68, 58, 50)}px">{html.escape(p["text"])}</div></div></div>''')
    bubbles.append(f'''<div id="s{c}" class="clip scene" data-start="{starts[c]}" data-duration="{secs[c]}" data-track-index="1">
      <div class="bubble"><div class="say heading" style="font-size:{_size(post["cta"], 80, 68, 58)}px">{html.escape(post["cta"])}</div>
      <div class="follow">Follow <b>@{html.escape(account["handle"])}</b></div></div></div>''')

    reaction = post.get("reaction", "shocked")
    js = [
        # Always alive: breathing bob, periodic blinks, burst hidden unless shocked/excited
        f'tl.to("#body", {{y: -12, duration: 0.9, repeat: {int(total / 0.9)}, yoyo: true, ease: "sine.inOut"}}, 0);',
        *[f'tl.to("#eyes", {{scaleY: 0.1, duration: 0.07, repeat: 1, yoyo: true, transformOrigin: "50% 50%"}}, {b});'
          for b in [round(x * 2.7 + 1.3, 2) for x in range(int(total / 2.7))]],
        # Hook: jump in with the reaction face
        'tl.fromTo("#mascot", {y: 500}, {y: 0, duration: 0.45, ease: "back.out(1.8)"}, 0);',
        f'tl.fromTo("#head", {{rotation: -6}}, {{rotation: 6, duration: 0.08, repeat: 5, yoyo: true, svgOrigin: "300 500"}}, 0.45);',
        'tl.fromTo("#s0 .bubble", {scale: 0.4, opacity: 0}, {scale: 1, opacity: 1, duration: 0.35, ease: "back.out(2.4)", '
        'transformOrigin: "50% 100%"}, 0.15);',
    ]
    if reaction in ("shocked", "excited"):
        js += ['tl.fromTo("#burst", {opacity: 0, y: 24}, {opacity: 1, y: 0, duration: 0.25, ease: "back.out(3)"}, 0.4);', f'tl.to("#burst", {{opacity: 0, duration: 0.2}}, {round(secs[0] - 0.3, 2)});']
    for i in range(1, n + 1):
        s = starts[i]
        js += [*_face(POINT_FACES[(i - 1) % len(POINT_FACES)], s),
               f'tl.to("#armR", {{rotation: -150, duration: 0.3, svgOrigin: "412 600", ease: "back.out(2)"}}, {s});',
               f'tl.to("#armR", {{rotation: -135, duration: 0.4, repeat: 3, yoyo: true, svgOrigin: "412 600", ease: "sine.inOut"}}, {s + 0.3});',
               f'tl.fromTo("#s{i} .bubble", {{y: 60, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.3, ease: "power3.out"}}, {s});',
               f'tl.fromTo("#s{i} .pill", {{scale: 0}}, {{scale: 1, duration: 0.3, ease: "back.out(3)"}}, {s + 0.1});']
    sc = starts[c]
    js += [*_face("excited", sc),
           f'tl.to("#armR", {{rotation: -160, duration: 0.25, svgOrigin: "412 600"}}, {sc});',
           f'tl.to("#armR", {{rotation: -125, duration: 0.25, repeat: 7, yoyo: true, svgOrigin: "412 600", ease: "sine.inOut"}}, {sc + 0.25});',
           f'tl.fromTo("#s{c} .bubble", {{scale: 0.6, opacity: 0}}, {{scale: 1, opacity: 1, duration: 0.35, ease: "back.out(2)", '
           f'transformOrigin: "50% 100%"}}, {sc});',
           f'tl.fromTo("#s{c} .follow", {{y: 30, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.3}}, {sc + 0.4});']

    return f'''<!doctype html>
<html lang="en" data-resolution="portrait"><head><meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="assets/gsap.min.js"></script>
<style>
{_font_faces(account)}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
#root {{ width: 1080px; height: 1920px; position: relative; overflow: hidden; background: {t["bg"]};
  font-family: '{t["body"]}', sans-serif; }}
#floor {{ position: absolute; left: 0; right: 0; bottom: 0; height: 420px; background: rgba(0,0,0,.12); }}
#stage {{ position: absolute; left: 160px; bottom: -150px; }}
.scene {{ position: absolute; inset: 0; }}
/* Starting face comes from CSS: HyperFrames doesn't reliably apply instant timeline sets at 0 s */
.brow, .mouth, #burst {{ opacity: 0; }}
#{FACES.get(reaction, FACES["happy"])[0]}, #{FACES.get(reaction, FACES["happy"])[1]} {{ opacity: 1; }}
.bubble {{ position: absolute; top: 170px; left: 70px; right: 70px; background: #fff; color: #111; border-radius: 56px;
  padding: 56px 60px; text-align: center; box-shadow: 0 18px 50px rgba(0,0,0,.25); }}
.bubble::after {{ content: ""; position: absolute; bottom: -54px; left: 46%; border: 30px solid transparent;
  border-top: 34px solid #fff; border-bottom: 0; }}
.heading {{ font-family: '{t["heading"]}', sans-serif; font-weight: 800; line-height: 1.12; }}
.say {{ line-height: 1.25; font-weight: 600; }}
.pill {{ display: inline-block; background: {t["accent"]}; color: {t["on_accent"]}; font-weight: 800; font-size: 40px;
  padding: 10px 28px; border-radius: 999px; margin-bottom: 30px; }}
.follow {{ margin-top: 34px; font-size: 46px; font-weight: 600; }}
.follow b {{ color: {t["accent"] if t["on_accent"] == "#FFFFFF" else "#111"}; }}
.handle {{ position: absolute; top: 80px; width: 100%; text-align: center; font-size: 34px; font-weight: 600;
  color: {t["text"]}; opacity: .8; }}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1080" data-height="1920">
  <div id="world" class="clip" data-start="0" data-duration="{total}" data-track-index="0">
    <div id="floor"></div><div class="handle">@{html.escape(account["handle"])}</div>
    <div id="stage">{character(look)}</div></div>
  {"".join(bubbles)}
  <audio id="music" data-start="0" data-duration="{total}" data-track-index="2" data-volume="0.8" src="assets/music.mp3"></audio>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
window.__timelines["main"] = tl;
tl.seek(0);
</script></body></html>'''


def render(post: dict, account: dict, music: Path, out: Path) -> Path:
    return render_project(composition(post, account, durations(post)), music, out)
