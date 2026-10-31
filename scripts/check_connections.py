"""Checks every credential and reports the result to Telegram.

Run: python -m scripts.check_connections
"""
import requests

from engine import db, instagram, llm, storage, telegram
from engine.config import ig_token, load_accounts

results = []

for acc in load_accounts()["accounts"]:
    try:
        info = instagram.me(ig_token(acc["id"]))
        ok = info["username"].lower() == acc["handle"].lower()
        note = f"@{info['username']} ({info['account_type']})"
        if not ok:
            note += f" - expected @{acc['handle']}, token belongs to a different account"
        results.append((ok, f"Instagram {acc['id']}", note))
    except Exception as e:
        results.append((False, f"Instagram {acc['id']} (@{acc['handle']})", str(e)))

for fast in (False, True):
    name = f"AI ({llm.model_for(fast)})"
    try:
        reply = llm.complete("Reply with exactly: OK", max_tokens=1024, fast=fast)
        results.append(("OK" in reply, name, reply.strip()[:40]))
    except Exception as e:
        results.append((False, name, str(e)))

try:
    db.ping()
    results.append((True, "Supabase", "connected"))
except Exception as e:
    results.append((False, "Supabase", str(e)))

try:
    key = "healthcheck/ping.txt"
    url = storage.upload_bytes(key, b"ok", "text/plain")
    public = requests.get(url, timeout=30)
    storage.delete(key)
    ok = public.status_code == 200 and public.text == "ok"
    results.append((ok, "R2", "upload + public URL working" if ok else f"public URL returned {public.status_code}"))
except Exception as e:
    results.append((False, "R2", str(e)))

lines = [f"{'✅' if ok else '❌'} {name}: {note}" for ok, name, note in results]
report = "Beesz content engine - connection check\n\n" + "\n".join(lines)
print(report)

try:
    telegram.send_message(report)
    print("\n✅ Telegram: report sent")
except Exception as e:
    print(f"\n❌ Telegram: {e}")
    raise SystemExit(1)

if not all(ok for ok, _, _ in results):
    raise SystemExit(1)
