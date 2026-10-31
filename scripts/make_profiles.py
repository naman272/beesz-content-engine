"""Renders a 1080x1080 profile photo per account (content kept inside the circle crop)
and sends photos + names + bios to Telegram.

Run: python -m scripts.make_profiles
"""
import yaml
from playwright.sync_api import sync_playwright

from engine import telegram
from engine.config import ROOT, load_accounts
from engine.render.carousel import FONTS_CSS, _theme

OUT = ROOT / "output" / "profiles"

# One small icon per persona, drawn in the accent color
ICONS = {
    "acc1": '<rect x="0" y="0" width="120" height="16" rx="3"/>',                                   # bold bar
    "acc2": '<path d="M60 70 C 60 30, 30 20, 10 22 C 12 46, 30 62, 60 70 Z M60 70 C 60 40, 85 26, 110 28 C 106 52, 86 66, 60 70 Z"/>',  # leaf
    "acc3": '<polyline points="0,60 30,40 55,50 85,15 120,22" fill="none" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>',  # chart
    "acc4": '<polygon points="70,0 20,70 55,70 45,120 100,45 63,45"/>',                              # bolt
    "acc5": '<path d="M10 70 Q10 20 50 10 L54 24 Q30 34 32 50 L50 50 L50 90 L10 90 Z M66 70 Q66 20 106 10 L110 24 Q86 34 88 50 L106 50 L106 90 L66 90 Z"/>',  # quote
}


def page(account: dict, monogram: str) -> str:
    t = _theme(account)
    icon = ICONS[account["id"]]
    stroke = f'stroke="{t["accent"]}"' if account["id"] == "acc3" else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS_CSS}">
<style>* {{ margin:0; padding:0; }}
body {{ width:1080px; height:1080px; background:{t['bg']}; display:flex; align-items:center; justify-content:center; }}
.wrap {{ display:flex; flex-direction:column; align-items:center; gap:36px; }}
.mono {{ font-family:'{t['heading']}', sans-serif; font-weight:900; font-size:360px; line-height:.9;
  color:{t['text']}; letter-spacing:-0.03em; }}
svg {{ fill:{t['accent']}; }}
</style></head><body><div class="wrap">
<div class="mono">{monogram}</div>
<svg width="230" height="230" viewBox="0 0 120 120" {stroke}>{icon}</svg>
</div></body></html>"""


def main() -> None:
    profiles = yaml.safe_load((ROOT / "config" / "profiles.yaml").read_text())["profiles"]
    OUT.mkdir(parents=True, exist_ok=True)
    paths = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        tab = browser.new_page(viewport={"width": 1080, "height": 1080})
        for account in load_accounts()["accounts"]:
            html = OUT / f"{account['id']}.html"
            html.write_text(page(account, profiles[account["id"]]["monogram"]))
            tab.goto(html.as_uri())
            tab.evaluate("document.fonts.ready")
            paths[account["id"]] = OUT / f"{account['handle']}.png"
            tab.screenshot(path=str(paths[account["id"]]))
        browser.close()

    if "--send" in __import__("sys").argv:
        for account in load_accounts()["accounts"]:
            prof = profiles[account["id"]]
            telegram.send_photos([paths[account["id"]]],
                                 f"@{account['handle']}\n\nNAME:\n{prof['name']}\n\nBIO:\n{prof['bio']}")
    print("\n".join(str(p) for p in paths.values()))


if __name__ == "__main__":
    main()
