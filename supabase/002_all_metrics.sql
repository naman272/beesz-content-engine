-- Adds every per-post metric Instagram exposes, plus daily account stats.
-- Paste into Supabase: SQL Editor -> New query -> Run.

alter table metrics
  add column if not exists reposts              int,
  add column if not exists total_interactions   int,
  add column if not exists profile_visits       int,
  add column if not exists profile_activity     int,
  add column if not exists follows              int,
  add column if not exists avg_watch_time_ms    int,
  add column if not exists total_watch_time_ms  bigint,
  add column if not exists skip_rate            numeric,
  add column if not exists raw                  jsonb;   -- everything returned, incl. breakdowns

create table if not exists account_stats (
  id            bigint generated always as identity primary key,
  account_id    text not null,
  captured_at   timestamptz not null default now(),
  followers     int,
  follows       int,
  media_count   int
);
create index if not exists account_stats_account on account_stats (account_id, captured_at desc);
alter table account_stats enable row level security;
