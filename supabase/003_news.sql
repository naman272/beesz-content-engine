-- Breaking-news posts. Paste into Supabase: SQL Editor -> New query -> Run.

create table if not exists news_items (
  id            bigint generated always as identity primary key,
  url           text not null unique,
  source        text,
  title         text not null,
  published_at  timestamptz,
  score         int,
  takeaway      text,
  reason        text,
  account_id    text,
  post_id       uuid references posts(id) on delete set null,
  created_at    timestamptz not null default now()
);
create index if not exists news_items_created on news_items (created_at desc);
alter table news_items enable row level security;

alter table posts
  add column if not exists kind        text not null default 'evergreen',   -- evergreen | news
  add column if not exists source_url  text;
