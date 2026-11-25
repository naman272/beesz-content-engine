# Beesz Content Engine: notes for Claude sessions

Fully automated faceless Instagram content for early-stage founders (mostly India). The owner wants it to
run hands-off: never add manual steps (reposting, approvals, daily chores). Reports are informational.

## Accounts
5 Instagram creator accounts, config in `config/accounts.yaml`: acc1 founder.world1 (Blunt Operator),
acc2 founder.space1 (Calm Mentor), acc3 founderspace1 (Data Nerd), acc4 foundr.world (Hype Builder),
acc5 foundr_world (Storyteller, real company stories only). Profiles in `config/profiles.yaml`.

## Where things run
- This repo is **public** (unlimited GitHub Actions minutes). Never commit media or secrets.
- Licensed media (stock images, music, purchased reaction clips) lives in the **private** repo
  `naman272/beesz-content-media`, checked out at `media/` (workflows use the `MEDIA_DEPLOY_KEY` secret).
  New media: drop raw files in `assets/backgrounds/<category>/` or `assets/music/<mood>/`, run
  `python -m scripts.prepare_assets`, then commit and push inside `media/`.
- Old private repo with full history: `naman272/beesz-content-engine-archive` (jobs disabled).
- Supabase (posts, metrics, hooks, batches, news_items, ig_tokens, account_stats), Cloudflare R2 (rendered
  media, public r2.dev URL for Instagram), Telegram (reports), Anthropic (Opus 5.5 writes via Batch API,
  Haiku 5.5 filters). Secrets: `.env` locally, GitHub Secrets in CI. `PUBLISHING_ENABLED` repo variable.

## Jobs (.github/workflows)
- `weekly-review` ("Weekly review and plan") Sunday 01:00 IST: scorecard + analysis of the week, learnings saved to
  output/weekly_insights.json, then `plan_week` plans and writes Sunday-Saturday in one batch with those
  learnings in the brief. The owner wants planning ONLY on Sundays: no mid-week re-plans or refills.
- `plan-week`: manual only now (same planner).
- `scheduler` (since 21 Nov 2026): one ~5.5h job looping `scripts/scheduler.py`: publish every 10 min, collect
  batches every 30 min, news + render (posts due in 8h) hourly, Telegram inbox every 3h. Each run queues its
  successor when it starts (concurrency group `scheduler`); a backup cron restarts a broken chain. Reason: GitHub
  cron dropped to ~3 runs/day from 14 Nov, so posts went out hours late in bursts. `hourly`, `render` and
  `telegram-inbox` workflows are manual-only now (no cron) to avoid double publishing.
- Render: Animated formats use HyperFrames (Node 22).
- `nightly`: metrics (all IG insights), winners (>=1000 views or 3x account median within ~72h), daily
  report, token refresh, media cleanup. Each step isolated.
- Telegram inbox (in the scheduler, every 3h): reads links/videos/notes the owner sends the bot (private chat), analyses
  them with Haiku (frames via yt-dlp/ffmpeg), saves as `hooks` source=reference (fed into the winner share),
  replies to each message. Telegram keeps unread updates only 24h. No webhook by owner's choice.
- `keepalive` weekly: re-enables schedules (public repos pause them after 60 days without commits).

## Content strategy (decided with the owner)
- Reels-first (~85%). Hooks: controversial, written like a real person reacting ("wait you did X??"),
  never AI-template phrasing ("Unpopular opinion:", "POV:"); enforced in `engine/checks.py`.
- No invented stories/characters. Real sources: Reddit founder questions (`config/sources.yaml`, 18 subs),
  company breakdowns (news + Wikipedia), India schemes/grants guides (1 source enough, no "verify with a
  CA" line, short 4 points), weekly funding roundup, breaking news (`config/news.yaml`).
- **40% exploit / 60% explore** (`exploit_share`): 40% of slots reuse the current winning pattern on new
  topics (`kind: winner`), the rest explore other content. Don't let winners homogenize everything.
- Formats: reaction (clips), carousel, and from 2026-11-04 (`format_switch_date`) 2D animated formats:
  chat, myth_fact, checklist, animated (`engine/render/formats2d.py`, `animated.py`, presenter character in `presenter.py`),
  and explainer (narrated, free Kokoro voice at 1.2x, one voice per account; `engine/render/explainer.py`,
  `engine/voice.py`, spec in `docs/explainer-format.md`), 15% of each account's mix.
  Presenter (explainer, myth_fact, checklist): 12 illustrated poses in `media/library/characters/shared/` (raw in
  gitignored `assets/characters/`). Owner makes more poses/characters in ChatGPT on request. Never use the old mascot.
- 25 Nov 2026 (owner): goal is 50k-100k-view Reels. Company breakdowns as Reels are the best angle (median 170,
  4 of top 5 ever), so they're back on every account (foundr_world 60%); "big swing" track = household-name Indian
  brands first in `config/sources.yaml` + mass-audience breakdown guide (shocking checkable fact in the hook,
  twist, lesson, debatable question CTA). Advice topics weighted to starting_up. Funding roundup off (0 views).
  No "confirm with a CA/lawyer" disclaimers anywhere. Founder questions: Reddit blocks GitHub servers, so the
  scheduler pools Reddit + Ask HN threads hourly on R2 (`pools/reddit.json`) for Sunday's plan.
- Own-product promos (`config/promos.yaml`, `engine/promos.py`): `kind: promo`, always reaction Reels with a live
  screen capture of the site (`engine/render/site.py`) and a link-in-bio card. Each active promo takes `share`
  (10%) of the weekly plan; facts only from its brief; promos never become winners. Bio links point to the
  promo. Replymaxxing promo ran 12-25 Nov 2026, stopped by the owner (no promo active).
- Changes to content strategy go through the owner; a 1-week hook test ran 28 Oct - 3 Nov.

## Known gotchas
- Meta app rate limit: publishing pauses at 75% usage and retries next hour; a post is recorded as
  published as soon as `media_publish` succeeds; retries check for an already-live duplicate.
- IG insights: `reposts` metric is rejected; unsupported metrics are dropped automatically.
- Reddit RSS from GitHub runners needs spacing/retries (handled in `engine/sources.py`).
- HyperFrames: initial state must come from CSS (timeline `set` at t=0 isn't reliable); telemetry disabled.

## Pending / ideas
- X (Twitter) pilot after the test: 2 accounts, pay-per-use API (~$0.015/post, avoid links), unique
  content per account, "Automated" label required.
- More reaction clips from 3-4 creators would reduce face repetition.
