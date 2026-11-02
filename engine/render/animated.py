"""Animated text Reel (2D motion graphics) rendered with HyperFrames: HTML + GSAP -> MP4.

Uses the same script data as reaction Reels (hook, points, cta, music_mood), so any reaction post can be
rendered this way. Layout: hook words pop in -> one animated scene per point -> follow card.
"""
import html
import json
import re
import shutil
import subprocess
from pathlib import Path

from engine import assets
from engine.config import ROOT
from engine.render.carousel import _theme

HYPERFRAMES = "hyperframes@0.8.212"
FONTS = ROOT / "assets" / "fonts"
GSAP = ROOT / "assets" / "vendor" / "gsap.min.js"


def _read_time(text: str, lo: float, hi: float, extra: float = 0.4) -> float:
    """Reading rule: about 0.5 s + 0.3 s per word, plus time for the words to animate in."""
    return round(min(hi, max(lo, 0.5 + 0.3 * len(text.split()) + extra)), 2)


def durations(post: dict) -> list[float]:
    hook = _read_time(post["hook"], 2.4, 3.6)
    points = [_read_time(p["text"], 1.8, 5.0) for p in post["points"]]
    cta = _read_time(post["cta"], 2.6, 4.2, extra=0.9)  # CTA line plus the follow line after it
    return [hook, *points, cta]


def _size(text: str, big: int, mid: int, small: int) -> int:
    return big if len(text) <= 30 else mid if len(text) <= 55 else small


def _words(text: str, cls: str) -> str:
    """Each word in its own span so it can animate; shouty words (CAPS, ??) get the accent colour."""
    out = []
    for w in text.split():
        hot = "??" in w or "!!" in w or (len(w) > 2 and w.isupper())
        out.append(f'<span class="{cls}{" hot" if hot else ""}">{html.escape(w)}</span>')
    return " ".join(out)


def _font_faces(account: dict) -> str:
    css = (FONTS / "fonts.css").read_text()
    wanted = {account["fonts"]["heading"], account["fonts"]["body"]}
    blocks = re.findall(r"@font-face \{.*?\}", css, flags=re.S)
    keep = [b for b in blocks if re.search(r"font-family: '([^']+)'", b).group(1) in wanted]
    return "\n".join(b.replace("url(", "url(assets/fonts/") for b in keep)


def composition(post: dict, account: dict, secs: list[float]) -> str:
    t = _theme(account)
    total = round(sum(secs), 2)
    starts = [round(sum(secs[:i]), 2) for i in range(len(secs))]
    n = len(post["points"])

    scenes = [f'''<div id="s0" class="clip scene" data-start="0" data-duration="{secs[0]}" data-track-index="1">
      <div class="hook heading" style="font-size:{_size(post["hook"], 112, 94, 80)}px">{_words(post["hook"], "w")}</div></div>''']
    for i, p in enumerate(post["points"], 1):
        scenes.append(f'''<div id="s{i}" class="clip scene" data-start="{starts[i]}" data-duration="{secs[i]}" data-track-index="1">
      <div class="pill">{i}/{n}</div>
      <div class="point heading" style="font-size:{_size(p["text"], 84, 70, 60)}px">{_words(p["text"], "w")}</div>
      <div class="bar"></div></div>''')
    c = len(secs) - 1
    scenes.append(f'''<div id="s{c}" class="clip scene" data-start="{starts[c]}" data-duration="{secs[c]}" data-track-index="1">
      <div class="cta heading">{_words(post["cta"], "w")}</div>
      <div class="follow">Follow <b>@{html.escape(account["handle"])}</b></div>
      <div class="arrow">&darr;</div></div>''')

    # Timeline: background drifts the whole time; each scene animates in, then out
    js = [f'tl.fromTo("#progress", {{scaleX: 0}}, {{scaleX: 1, duration: {total}, ease: "none"}}, 0);',
          f'tl.to("#blob1", {{x: 220, y: 380, duration: {total}, ease: "sine.inOut"}}, 0);',
          f'tl.to("#blob2", {{x: -260, y: -300, duration: {total}, ease: "sine.inOut"}}, 0);',
          f'tl.to("#blob3", {{x: 160, y: -220, scale: 1.3, duration: {total}, ease: "sine.inOut"}}, 0);',
          'tl.fromTo("#s0 .w", {y: 90, opacity: 0, scale: 0.5}, {y: 0, opacity: 1, scale: 1, duration: 0.35, '
          'stagger: 0.07, ease: "back.out(2.2)"}, 0);',
          f'tl.fromTo("#s0 .hook", {{x: -10}}, {{x: 10, duration: 0.06, repeat: 5, yoyo: true, ease: "none"}}, '
          f'{round(min(secs[0] - 0.6, 0.35 + 0.07 * len(post["hook"].split())), 2)});']
    for i in range(1, n + 1):
        s = starts[i]
        js += [f'tl.fromTo("#s{i} .pill", {{scale: 0, rotation: -12}}, {{scale: 1, rotation: 0, duration: 0.3, ease: "back.out(3)"}}, {s});',
               f'tl.fromTo("#s{i} .w", {{y: 50, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.28, stagger: 0.04, ease: "power3.out"}}, {s + 0.1});',
               f'tl.fromTo("#s{i} .bar", {{scaleX: 0}}, {{scaleX: 1, duration: 0.5, ease: "power2.out"}}, {s + 0.3});',
               f'tl.to("#s{i} .point", {{y: -40, opacity: 0, duration: 0.2, ease: "power2.in"}}, {round(s + secs[i] - 0.2, 2)});']
    sc = starts[c]
    js += [f'tl.fromTo("#s{c} .w", {{scale: 0.6, opacity: 0}}, {{scale: 1, opacity: 1, duration: 0.3, stagger: 0.05, ease: "back.out(2)"}}, {sc});',
           f'tl.fromTo("#s{c} .follow", {{y: 40, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.3}}, {sc + 0.4});',
           f'tl.fromTo("#s{c} .arrow", {{y: -10}}, {{y: 14, duration: 0.3, repeat: 4, yoyo: true, ease: "sine.inOut"}}, {sc + 0.5});']

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
.blob {{ position: absolute; border-radius: 50%; background: {t["accent"]}; opacity: .14; filter: blur(60px); }}
#blob1 {{ width: 620px; height: 620px; left: -160px; top: 160px; }}
#blob2 {{ width: 540px; height: 540px; right: -140px; top: 1100px; }}
#blob3 {{ width: 420px; height: 420px; left: 300px; top: 700px; opacity: .1; }}
#progress {{ position: absolute; top: 0; left: 0; width: 1080px; height: 14px; background: {t["accent"]};
  transform-origin: left center; }}
.scene {{ position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 0 90px; text-align: center; }}
.heading {{ font-family: '{t["heading"]}', sans-serif; font-weight: 800; line-height: 1.12; letter-spacing: -0.01em; }}
.w {{ display: inline-block; }}
.hot {{ color: {t["accent"]}; }}
.hook {{ max-width: 920px; }}
.pill {{ background: {t["accent"]}; color: {t["on_accent"]}; font-weight: 800; font-size: 44px;
  padding: 12px 30px; border-radius: 999px; margin-bottom: 56px; }}
.point {{ max-width: 900px; }}
.bar {{ width: 160px; height: 12px; background: {t["accent"]}; margin-top: 56px; transform-origin: center; }}
.cta {{ font-size: 80px; max-width: 900px; }}
.follow {{ margin-top: 70px; font-size: 52px; font-weight: 600; }}
.follow b {{ color: {t["accent"]}; }}
.arrow {{ margin-top: 30px; font-size: 90px; color: {t["accent"]}; }}
.handle {{ position: absolute; bottom: 200px; width: 100%; text-align: center; font-size: 34px; opacity: .7; }}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1080" data-height="1920">
  <div id="bg" class="clip" data-start="0" data-duration="{total}" data-track-index="0">
    <div id="blob1" class="blob"></div><div id="blob2" class="blob"></div><div id="blob3" class="blob"></div>
    <div id="progress"></div><div class="handle">@{html.escape(account["handle"])}</div></div>
  {"".join(scenes)}
  <audio id="music" data-start="0" data-duration="{total}" data-track-index="2" data-volume="0.8" src="assets/music.mp3"></audio>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
window.__timelines["main"] = tl;
tl.seek(0);
</script></body></html>'''


_telemetry_off = False


def _disable_telemetry() -> None:
    """HyperFrames sends anonymous usage data by default; switch it off once per machine/run."""
    global _telemetry_off
    if not _telemetry_off:
        subprocess.run(["npx", "--yes", HYPERFRAMES, "telemetry", "disable"], check=False, capture_output=True)
        _telemetry_off = True


def render_project(page: str, music: Path, out: Path, extra: dict[str, Path] | None = None) -> Path:
    """Writes a HyperFrames project for `page` (fonts, GSAP, music) and renders it to `out`."""
    _disable_telemetry()
    project = out.parent / "hf_project"
    if project.exists():
        shutil.rmtree(project)
    (project / "assets" / "fonts").mkdir(parents=True)
    for f in FONTS.glob("*.woff2"):
        shutil.copy(f, project / "assets" / "fonts" / f.name)
    shutil.copy(GSAP, project / "assets" / "gsap.min.js")
    shutil.copy(music, project / "assets" / "music.mp3")
    for name, path in (extra or {}).items():
        shutil.copy(path, project / "assets" / name)
    (project / "index.html").write_text(page)
    (project / "meta.json").write_text(json.dumps({"id": "beesz-reel", "name": "beesz-reel"}))
    subprocess.run(["npx", "--yes", HYPERFRAMES, "render", str(project), "-o", str(out),
                    "--fps", "30", "--quality", "standard", "--quiet"], check=True)
    return out


def render(post: dict, account: dict, music: Path, out: Path) -> Path:
    return render_project(composition(post, account, durations(post)), music, out)
