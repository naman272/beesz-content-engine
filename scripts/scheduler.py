"""Runs the frequent jobs (publish, collect batches, news, render, Telegram inbox) on time inside one long
GitHub Actions job. GitHub's cron runs got throttled to ~3 a day from 14 Nov 2026, so posts went out in late
bursts; this loop doesn't depend on cron. The Scheduler workflow queues its successor when it starts, so the
chain keeps going (its own backup cron restarts it if the chain ever breaks).

Each task runs as its own process, so one failing or hanging task never stops the others.

Run: python -m scripts.scheduler [--hours 5.5]
"""
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

# (name, command, every N minutes, timeout minutes)
TASKS = [
    ("publish", ["python", "-m", "scripts.publish_due"], 10, 20),
    ("collect", ["python", "-m", "scripts.collect_batches"], 30, 30),
    ("news", ["python", "-m", "scripts.news_check"], 60, 20),
    # Breaking news is due immediately; the main render pass covers everything due in the next 8 hours
    ("render", ["python", "-m", "scripts.render_due", "--hours", "8"], 60, 60),
    ("inbox", ["python", "-m", "scripts.telegram_inbox"], 180, 20),
]


def run(name: str, cmd: list[str], timeout_min: int) -> None:
    if name == "publish" and os.environ.get("PUBLISHING_ENABLED") != "true":
        print("publish: switched off (repo variable PUBLISHING_ENABLED)", flush=True)
        return
    started = time.time()
    print(f"\n=== {datetime.now(timezone.utc):%H:%M} {name}", flush=True)
    try:
        code = subprocess.run(cmd, timeout=timeout_min * 60).returncode
    except subprocess.TimeoutExpired:
        code = "timeout"
    print(f"=== {name} done ({code}) in {time.time() - started:.0f}s", flush=True)
    if name == "news" and code == 0:  # render breaking news right away so it publishes on the next pass
        run("render-news", ["python", "-m", "scripts.render_due", "--hours", "1"], 20)


def main() -> None:
    hours = float(sys.argv[sys.argv.index("--hours") + 1]) if "--hours" in sys.argv else 5.5
    deadline = time.time() + hours * 3600
    last = {name: 0.0 for name, *_ in TASKS}
    while time.time() < deadline:
        for name, cmd, every, timeout_min in TASKS:
            if time.time() - last[name] >= every * 60 and time.time() < deadline:
                last[name] = time.time()
                run(name, cmd, timeout_min)
        time.sleep(30)
    print("Scheduler window over; the queued successor run takes over.")


if __name__ == "__main__":
    main()
