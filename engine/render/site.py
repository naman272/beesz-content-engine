"""Live screen capture of a website for promo Reels: a phone-width full-page screenshot taken at render time
(so the leaderboard numbers are current), turned into a slow scroll with the URL pinned at the bottom."""
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

from engine.render import overlays

W, H, FPS = 1080, 1920, 30
PHONE_W = 390  # CSS px; scaled up so the screenshot is exactly 1080 wide
SECONDS = 5.0
HOLD = 1.6  # seconds on the hero (headline + top 3) before scrolling
SCROLL_SCREENS = 1.3  # how far down to glide (in screen heights), to show the board


def screenshot(url: str, out: Path) -> Path:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": PHONE_W, "height": round(PHONE_W * H / W)},
                                device_scale_factor=W / PHONE_W, is_mobile=True, has_touch=True)
        page.goto(url if url.startswith("http") else f"https://{url}", wait_until="networkidle", timeout=60000)
        try:  # the leaderboard loads after the page; wait for it, but a capture without it is still fine
            page.wait_for_function("!document.body.innerText.includes('Loading…')", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(800)
        page.screenshot(path=str(out), full_page=True)
        browser.close()
    return out


def url_layer(url: str) -> str:
    return f"""<div class="layer"><div style="position:absolute;bottom:250px;width:100%;display:flex;justify-content:center">
      <div style="background:#0A0A0A;color:#fff;border-radius:999px;padding:26px 46px;font-size:52px;font-weight:800;
        box-shadow:0 10px 40px rgba(0,0,0,.45);font-family:sans-serif">{url}</div></div></div>"""


def render(url: str, account: dict, out: Path) -> Path:
    """Returns an mp4 clip (SECONDS long, silent) of the site scrolling, with the URL pill on top."""
    work = out.parent
    shot = screenshot(url, work / "site.png")
    pill = overlays.render([(url_layer(url), True)], account, work / "site_layers")[0]
    # y offset: hold on the top, then ease down (smoothstep) by SCROLL_SCREENS screens, clamped to the page
    travel = f"min({SCROLL_SCREENS}*{H}\\,ih-{H})"
    p = f"clip((t-{HOLD})/({SECONDS}-{HOLD}-0.4)\\,0\\,1)"
    y = f"{travel}*({p})*({p})*(3-2*({p}))"
    vf = (f"[0:v]crop={W}:{H}:0:'{y}',fps={FPS},format=yuv420p,setsar=1[s];"
          f"[s][1:v]overlay=0:0:shortest=1,format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", f"{SECONDS}", "-framerate", str(FPS),
                    "-i", str(shot), "-loop", "1", "-t", f"{SECONDS}", "-framerate", str(FPS), "-i", str(pill),
                    "-filter_complex", vf, "-map", "[v]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)], check=True)
    return out
