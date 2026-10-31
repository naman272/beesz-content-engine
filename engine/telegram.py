import json
from pathlib import Path

import requests

from engine.config import env


def _call(method: str, **kwargs) -> dict:
    token = env("TELEGRAM_BOT_TOKEN")
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", timeout=300, **kwargs)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram error: {data.get('description')}")
    return data["result"]


def send_message(text: str) -> None:
    _call("sendMessage", json={"chat_id": env("TELEGRAM_CHAT_ID"), "text": text[:4096]})


def send_photos(paths: list[Path], caption: str = "") -> None:
    """Sends up to 10 images as one album."""
    media, files = [], {}
    for i, p in enumerate(paths[:10]):
        media.append({"type": "photo", "media": f"attach://f{i}", **({"caption": caption[:1024]} if i == 0 and caption else {})})
        files[f"f{i}"] = open(p, "rb")
    try:
        _call("sendMediaGroup", data={"chat_id": env("TELEGRAM_CHAT_ID"), "media": json.dumps(media)}, files=files)
    finally:
        for f in files.values():
            f.close()


def send_video(path: Path, caption: str = "") -> None:
    with open(path, "rb") as f:
        _call("sendVideo", data={"chat_id": env("TELEGRAM_CHAT_ID"), "caption": caption[:1024],
                                 "supports_streaming": "true"}, files={"video": f})
