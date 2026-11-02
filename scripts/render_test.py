"""Renders fixed sample Reels and reports timing (checks HyperFrames and the voice work on this machine).

Run: python -m scripts.render_test [chat|explainer]
"""
import json
import sys
import time

from engine import assets
from engine.config import ROOT, load_accounts
from engine.render import explainer, formats2d

fmt = sys.argv[1] if len(sys.argv) > 1 else "chat"
post = json.loads((ROOT / "tests" / f"sample_{fmt}.json").read_text())
account = {a["id"]: a for a in load_accounts()["accounts"]}["acc1"]
music = assets.path(assets.pick_music("calm")["file"])
out_path = ROOT / "output" / "render_test" / f"{fmt}.mp4"
start = time.time()
out = explainer.render(post, account, music, out_path) if fmt == "explainer" else formats2d.render(fmt, post, account, music, out_path)
print(f"rendered {out} ({out.stat().st_size // 1024} KB) in {time.time() - start:.0f}s")
