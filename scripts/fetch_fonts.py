"""One-time: download the Google Fonts used by account templates into assets/fonts.

Run: python -m scripts.fetch_fonts
"""
import re

import requests

from engine.config import ROOT

FAMILIES = [
    "Archivo+Black",
    "Inter:wght@400;600;800",
    "Fraunces:wght@600;800",
    "Space+Grotesk:wght@500;700",
    "JetBrains+Mono:wght@400;700",
    "Montserrat:wght@800;900",
    "Poppins:wght@400;600;800",
    "DM+Serif+Display",
]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"

out = ROOT / "assets" / "fonts"
out.mkdir(parents=True, exist_ok=True)
url = "https://fonts.googleapis.com/css2?" + "&".join(f"family={f}" for f in FAMILIES) + "&display=block"
css = requests.get(url, headers={"User-Agent": UA}, timeout=60).text

# Keep only the latin subset blocks
blocks = re.findall(r"/\* latin \*/\s*(@font-face \{.*?\})", css, flags=re.S)
local_css = []
for block in blocks:
    family = re.search(r"font-family: '([^']+)'", block).group(1)
    weight = re.search(r"font-weight: (\d+)", block).group(1)
    font_url = re.search(r"url\((https://[^)]+)\)", block).group(1)
    name = f"{family.replace(' ', '')}-{weight}.woff2"
    (out / name).write_bytes(requests.get(font_url, timeout=60).content)
    local_css.append(block.replace(font_url, name))
    print("saved", name)

(out / "fonts.css").write_text("\n".join(local_css) + "\n")
