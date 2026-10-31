# Beesz Content Engine

Automated faceless Instagram content for founders: AI writes the posts, code renders
carousels and videos, GitHub Actions publishes and tracks them.

## Layout
- `config/accounts.yaml` – the 5 accounts: look, voice, format mix, posting times
- `media/` – licensed media (stock images, music, reaction clips) from the private repo
  `naman272/beesz-content-media`; clone it here for local runs. Workflows check it out with the
  `MEDIA_DEPLOY_KEY` secret (read-only deploy key).
- `engine/` – shared code (AI, Instagram, Telegram, config)
- `scripts/` – runnable jobs
- `.github/workflows/` – scheduled and manual jobs

## Local setup
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill in the values
.venv/bin/python -m scripts.check_connections
```

## GitHub setup
Add each value from `.env` as a repository secret
(Settings → Secrets and variables → Actions → New repository secret),
then run **Actions → Check connections → Run workflow**.
