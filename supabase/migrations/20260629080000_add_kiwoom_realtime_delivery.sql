create table if not exists public.kiwoom_realtime_quotes (
  code text primary key,
  name text not null default '',
  price numeric,
  change_rate numeric,
  industry text not null default '',
  market text not null default '',
  kiwoom_rest_code text,
  proxy_code text,
  error text,
  payload jsonb not null default '{}'::jsonb,
  collected_at timestamptz not null,
  updated_at timestamptz not null default now()
);

create index if not exists kiwoom_realtime_quotes_updated_idx
  on public.kiwoom_realtime_quotes (updated_at desc);

alter table public.kiwoom_realtime_quotes enable row level security;

drop policy if exists "authenticated users read realtime quotes"
  on public.kiwoom_realtime_quotes;
create policy "authenticated users read realtime quotes"
  on public.kiwoom_realtime_quotes for select to authenticated
  using (
    exists (
      select 1 from public.user_profiles profile
      where profile.user_id = (select auth.uid())
        and profile.must_change_password = false
    )
  );

revoke all on public.kiwoom_realtime_quotes from anon, authenticated;
grant select on public.kiwoom_realtime_quotes to authenticated;
grant select, insert, update, delete on public.kiwoom_realtime_quotes to service_role;

create table if not exists public.dashboard_live_versions (
  dashboard_key text primary key check (dashboard_key in ('stock')),
  storage_bucket text not null,
  storage_path text not null,
  version text not null,
  quote_count integer not null default 0 check (quote_count >= 0),
  available_count integer not null default 0 check (available_count >= 0),
  updated_at timestamptz not null default now()
);

alter table public.dashboard_live_versions enable row level security;

drop policy if exists "authenticated users read live dashboard versions"
  on public.dashboard_live_versions;
create policy "authenticated users read live dashboard versions"
  on public.dashboard_live_versions for select to authenticated
  using (
    exists (
      select 1 from public.user_profiles profile
      where profile.user_id = (select auth.uid())
        and profile.must_change_password = false
    )
  );

revoke all on public.dashboard_live_versions from anon, authenticated;
grant select on public.dashboard_live_versions to authenticated;
grant select, insert, update, delete on public.dashboard_live_versions to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('dashboard-live', 'dashboard-live', false, 5242880, array['text/html'])
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "authenticated users read live dashboards" on storage.objects;
create policy "authenticated users read live dashboards"
  on storage.objects for select to authenticated
  using (
    bucket_id = 'dashboard-live'
    and exists (
      select 1 from public.user_profiles profile
      where profile.user_id = (select auth.uid())
        and profile.must_change_password = false
    )
  );

