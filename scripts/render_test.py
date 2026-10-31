"""Renders a fixed sample chat Reel and reports timing (checks HyperFrames works on this machine).

Run: python -m scripts.render_test
"""
import json
import time

from engine import assets
from engine.config import ROOT, load_accounts
from engine.render import formats2d

post = json.loads((ROOT / "tests" / "sample_chat.json").read_text())
account = {a["id"]: a for a in load_accounts()["accounts"]}["acc1"]
start = time.time()
out = formats2d.render("chat", post, account, assets.path(assets.pick_music("calm")["file"]),
                       ROOT / "output" / "render_test" / "reel.mp4")
print(f"rendered {out} ({out.stat().st_size // 1024} KB) in {time.time() - start:.0f}s")
