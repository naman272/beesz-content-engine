"""Renders 1080x1920 text layers for videos with Playwright (transparent PNGs, or opaque cards)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

from engine.render.carousel import FIT_JS, FONTS_CSS, _text, _theme

W, H = 1080, 1920

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: %(W)spx; height: %(H)spx; background: transparent; }
.layer { width: %(W)spx; height: %(H)spx; position: relative; overflow: hidden; }
.heading { font-family: '%(heading)s', sans-serif; font-weight: 800; line-height: 1.12; }
.fit { overflow: visible; }

/* hook over the reaction clip: white caption box, upper third */
.hookbox { position: absolute; top: 250px; left: 70px; right: 70px; display: flex; justify-content: center; }
.hookbox .box { background: #fff; color: #0A0A0A; border-radius: 28px; padding: 34px 40px;
  text-align: center; max-width: 940px; max-height: 470px; box-shadow: 0 10px 40px rgba(0,0,0,.35); }

/* text scene over a background image */
.scene .shade { position: absolute; inset: 0;
  background: radial-gradient(ellipse at center, rgba(0,0,0,.72) 0%%, rgba(0,0,0,.55) 55%%, rgba(0,0,0,.35) 100%%); }
.scene .content { position: absolute; left: 90px; right: 90px; top: 50%%; transform: translateY(-50%%);
  text-align: center; color: #fff; }
.scene .count { display: inline-block; background: %(accent)s; color: %(on_accent)s; font-weight: 800;
  font-size: 40px; padding: 10px 26px; border-radius: 999px; margin-bottom: 44px; font-family: '%(body)s', sans-serif; }
.scene .line { max-height: 640px; text-shadow: 0 4px 24px rgba(0,0,0,.6); }
.scene .bar { width: 120px; height: 10px; background: %(accent)s; margin: 44px auto 0; }

/* closing card */
.cta { background: %(bg)s; color: %(text)s; }
.cta .content { position: absolute; left: 90px; right: 90px; top: 50%%; transform: translateY(-50%%); text-align: center; }
.cta .main { max-height: 640px; }
.cta .follow { margin-top: 60px; font-family: '%(body)s', sans-serif; font-size: 48px; font-weight: 600; }
.cta .follow b { color: %(accent)s; }

.handle { position: absolute; bottom: 230px; width: 100%%; text-align: center; color: #fff;
  font-family: '%(body)s', sans-serif; font-size: 34px; font-weight: 600; opacity: .85;
  text-shadow: 0 2px 12px rgba(0,0,0,.6); }
"""


def hook_layer(text: str) -> str:
    return f'<div class="layer"><div class="hookbox"><div class="box heading fit" data-max="68" data-min="40">{_text(text)}</div></div></div>'


def scene_layer(text: str, index: int, total: int, handle: str) -> str:
    return f"""<div class="layer scene"><div class="shade"></div><div class="content">
      <div class="count">{index}/{total}</div>
      <div class="line heading fit" data-max="84" data-min="48">{_text(text)}</div>
      <div class="bar"></div></div><div class="handle">@{handle}</div></div>"""


def cta_layer(text: str, handle: str, link: str | None = None) -> str:
    """link: for promos, point to the link in bio instead of asking for a follow."""
    follow = f"<b>{link}</b>" if link else f"Follow <b>@{handle}</b> for more"
    return f"""<div class="layer cta"><div class="content">
      <div class="main heading fit" data-max="88" data-min="52">{_text(text)}</div>
      <div class="follow">{follow}</div></div></div>"""


def render(layers: list[tuple[str, bool]], account: dict, out_dir: Path) -> list[Path]:
    """layers: (html, transparent). Returns one PNG per layer."""
    out_dir.mkdir(parents=True, exist_ok=True)
    css = CSS % {"W": W, "H": H, **_theme(account)}
    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        for i, (layer, transparent) in enumerate(layers):
            doc = out_dir / f"layer_{i:02d}.html"
            doc.write_text(f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS_CSS}">'
                           f"<style>{css}</style></head><body>{layer}</body></html>")
            page.goto(doc.as_uri())
            page.evaluate("document.fonts.ready")
            page.locator(".fit").evaluate_all(FIT_JS)
            path = out_dir / f"layer_{i:02d}.png"
            page.screenshot(path=str(path), omit_background=transparent)
            paths.append(path)
        browser.close()
    return paths
