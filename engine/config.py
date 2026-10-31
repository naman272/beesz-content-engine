import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def env(name: str, required: bool = True) -> str:
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise RuntimeError(f"Missing {name} (set it in .env or GitHub secrets)")
    return value


def load_accounts() -> dict:
    with open(ROOT / "config" / "accounts.yaml") as f:
        return yaml.safe_load(f)


def ig_token(account_id: str) -> str:
    return env(f"IG_TOKEN_{account_id.upper()}")
