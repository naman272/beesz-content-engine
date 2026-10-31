"""Renders a carousel post into 1080x1350 JPEG slides with Playwright (HTML -> image)."""
import html
from pathlib import Path

from playwright.sync_api import sync_playwright

from engine import assets
from engine.config import ROOT

FONTS_CSS = (ROOT / "assets" / "fonts" / "fonts.css").as_uri()
W, H = 1080, 1350


def _luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _text(value: str) -> str:
    return html.escape(value.replace("**", "").strip()).replace("\n", "<br>")


def _theme(account: dict) -> dict:
    c = account["colors"]
    bg = f"linear-gradient(160deg, {c['bg_gradient'][0]}, {c['bg_gradient'][1]})" if "bg_gradient" in c else c["bg"]
    return {
        "bg": bg,
        "text": c["text"],
        "accent": c["accent"],
        "on_accent": "#0A0A0A" if _luminance(c["accent"]) > 0.5 else "#FFFFFF",
        "heading": account["fonts"]["heading"],
        "body": account["fonts"]["body"],
    }


CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { width: %(W)spx; background: #000; }
.slide { width: %(W)spx; height: %(H)spx; position: relative; overflow: hidden;
  background: %(bg)s; color: %(text)s; font-family: '%(body)s', sans-serif; }
.heading { font-family: '%(heading)s', serif; font-weight: 800; line-height: 1.08; letter-spacing: -0.01em; }
.handle { position: absolute; left: 72px; bottom: 56px; font-size: 30px; opacity: .75; font-weight: 600; }
.count { position: absolute; right: 72px; bottom: 56px; font-size: 30px; opacity: .6; font-weight: 600; }
.pill { display: inline-block; background: %(accent)s; color: %(on_accent)s; font-weight: 800;
  font-size: 30px; padding: 14px 28px; border-radius: 999px; }
.fit { overflow: visible; }

/* cover: photo */
.cover-photo img { position: absolute; inset: 0; width: 100%%; height: 100%%; object-fit: cover; }
.cover-photo .shade { position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(0,0,0,.25) 0%%, rgba(0,0,0,.35) 35%%, rgba(0,0,0,.88) 72%%); }
.cover-photo .content { position: absolute; left: 72px; right: 72px; bottom: 140px; color: #fff; }
.cover-photo .handle { color: #fff; }
.cover-photo .hook { max-height: 470px; }
.cover-photo .bar { width: 120px; height: 12px; background: %(accent)s; margin-bottom: 36px; }

/* cover: illustration */
.cover-illu .frame { position: absolute; top: 72px; left: 72px; right: 72px; height: 640px;
  border-radius: 36px; overflow: hidden; }
.cover-illu .frame img { width: 100%%; height: 100%%; object-fit: cover; }
.cover-illu .content { position: absolute; top: 760px; left: 72px; right: 72px; }
.cover-illu .hook { max-height: 330px; }

.subtitle { font-size: 38px; line-height: 1.3; margin-top: 24px; opacity: .92; }
.kicker { display: inline-block; background: %(accent)s; color: %(on_accent)s; font-weight: 800; font-size: 30px;
  letter-spacing: .08em; padding: 10px 22px; border-radius: 8px; margin-bottom: 28px; }
.source { margin-top: 36px; font-size: 30px; opacity: .7; }
.swipe { margin-top: 36px; }

/* point slides */
.point .num { position: absolute; top: 96px; left: 72px; font-family: '%(heading)s', serif;
  font-weight: 800; font-size: 150px; line-height: 1; color: %(accent)s; }
.point .title { position: absolute; bottom: 750px; left: 72px; right: 72px; max-height: 330px; }
.point .rule { position: absolute; top: 636px; left: 72px; width: 96px; height: 8px; background: %(accent)s; }
.point .body { position: absolute; top: 690px; left: 72px; right: 72px; max-height: 500px; line-height: 1.42; }

/* cta */
.cta .content { position: absolute; top: 50%%; left: 72px; right: 72px; transform: translateY(-55%%); }
.cta .main { max-height: 520px; }
.cta .actions { margin-top: 40px; font-size: 40px; line-height: 1.6; }
.cta .actions b { color: %(accent)s; }
"""

FIT_JS = """
(nodes) => nodes.forEach(el => {
  const max = +el.dataset.max, min = +el.dataset.min;
  const limit = parseFloat(getComputedStyle(el).maxHeight);
  let size = max;
  el.style.fontSize = size + 'px';
  // Some fonts overhang their line box by a few px, so only shrink past the real limit
  while ((el.scrollHeight > limit + 6 || el.scrollWidth > el.clientWidth + 2) && size > min) {
    size -= 2; el.style.fontSize = size + 'px';
  }
})
"""


def _slides_html(post: dict, account: dict, bg: dict) -> list[str]:
    handle = f"@{account['handle']}"
    total = len(post["slides"]) + 2
    img = assets.path(bg["file"]).as_uri()
    hook = _text(post["hook"])
    kicker = f'<div><span class="kicker">{_text(post["kicker"])}</span></div>' if post.get("kicker") else ""
    source = f'<div class="source">Source: {_text(post["source_name"])}</div>' if post.get("source_name") else ""
    subtitle = _text(post["cover_subtitle"])

    if bg["style"] == "photo":
        cover = f"""<div class="slide cover-photo"><img src="{img}"><div class="shade"></div>
          <div class="content">{kicker or '<div class="bar"></div>'}
            <div class="hook fit heading" data-max="104" data-min="56">{hook}</div>
            <div class="subtitle">{subtitle}</div>
            <div class="swipe"><span class="pill">Swipe &rarr;</span></div></div>
          <div class="handle">{handle}</div></div>"""
    else:
        cover = f"""<div class="slide cover-illu"><div class="frame"><img src="{img}"></div>
          <div class="content">{kicker}
            <div class="hook fit heading" data-max="88" data-min="48">{hook}</div>
            <div class="subtitle">{subtitle}</div></div>
          <div class="handle">{handle}</div><div class="count"><span class="pill">Swipe &rarr;</span></div></div>"""

    slides = [cover]
    for i, s in enumerate(post["slides"], 1):
        slides.append(f"""<div class="slide point"><div class="num">{i:02d}</div>
          <div class="title fit heading" data-max="76" data-min="44">{_text(s['title'])}</div>
          <div class="rule"></div>
          <div class="body fit" data-max="46" data-min="30">{_text(s['body'])}</div>
          <div class="handle">{handle}</div><div class="count">{i + 1}/{total}</div></div>""")

    slides.append(f"""<div class="slide cta"><div class="content">
        <div class="main fit heading" data-max="84" data-min="48">{_text(post['cta'])}</div>
        {source}<div class="actions">Save this for later.<br>Send it to a founder who needs it.<br>
          Follow <b>{handle}</b> for more.</div></div>
      <div class="handle">{handle}</div><div class="count">{total}/{total}</div></div>""")
    return slides


def render(post: dict, account: dict, bg: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    css = CSS % {"W": W, "H": H, **_theme(account)}
    body = "\n".join(_slides_html(post, account, bg))
    page_html = f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS_CSS}"><style>{css}</style></head><body>{body}</body></html>'
    html_path = out_dir / "slides.html"
    html_path.write_text(page_html)

    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        page.goto(html_path.as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_load_state("networkidle")
        page.locator(".fit").evaluate_all(FIT_JS)
        for i, slide in enumerate(page.locator(".slide").all(), 1):
            path = out_dir / f"slide_{i:02d}.jpg"
            slide.screenshot(path=str(path), type="jpeg", quality=92)
            paths.append(path)
        browser.close()
    return paths
