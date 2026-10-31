-- Beesz content engine schema. Paste into Supabase: SQL Editor -> New query -> Run.

create table if not exists batches (
  id            uuid primary key default gen_random_uuid(),
  provider_id   text not null,               -- Anthropic batch id
  week_start    date not null,
  status        text not null default 'submitted',   -- submitted | collected | failed
  plan          jsonb not null,               -- custom_id -> slots, angles
  usage         jsonb,                        -- token usage and cost once collected
  created_at    timestamptz not null default now(),
  collected_at  timestamptz
);

create table if not exists posts (
  id              uuid primary key default gen_random_uuid(),
  account_id      text not null,
  format          text not null,              -- carousel | reaction
  topic           text not null,
  hook_type       text,
  hook            text not null,
  content         jsonb not null,             -- full AI output
  assets          jsonb,                      -- files picked at render time
  status          text not null default 'planned',  -- planned | ready | published | failed | dropped
  scheduled_at    timestamptz not null,
  media_keys      jsonb,                      -- R2 object keys
  ig_media_id     text,
  permalink       text,
  published_at    timestamptz,
  error           text,
  batch_id        uuid references batches(id),
  created_at      timestamptz not null default now()
);
create index if not exists posts_due on posts (status, scheduled_at);
create index if not exists posts_account on posts (account_id, scheduled_at desc);

create table if not exists metrics (
  id            bigint generated always as identity primary key,
  post_id       uuid not null references posts(id) on delete cascade,
  captured_at   timestamptz not null default now(),
  hours_live    numeric,
  views         int, reach int, likes int, comments int, saves int, shares int
);
create index if not exists metrics_post on metrics (post_id, captured_at desc);

create table if not exists hooks (
  id            bigint generated always as identity primary key,
  hook          text not null,
  hook_type     text,
  format        text,
  topic         text,
  source        text not null,                -- winner | reference | manual
  account_id    text,
  post_id       uuid references posts(id) on delete set null,
  views         int,
  active        boolean not null default true,
  created_at    timestamptz not null default now(),
  unique (post_id)
);

create table if not exists ig_tokens (
  account_id    text primary key,
  token         text not null,
  refreshed_at  timestamptz not null default now()
);

-- Only the service key (used by the engine) can read or write these tables.
alter table batches enable row level security;
alter table posts enable row level security;
alter table metrics enable row level security;
alter table hooks enable row level security;
alter table ig_tokens enable row level security;
