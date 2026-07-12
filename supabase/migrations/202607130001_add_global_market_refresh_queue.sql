create table if not exists public.global_market_refresh_requests (
  id uuid primary key default gen_random_uuid(),
  request_type text not null default 'batch'
    check (request_type in ('single', 'batch', 'full', 'domestic_auto')),
  securities jsonb not null default '[]'::jsonb,
  status text not null default 'pending'
    check (status in ('pending', 'processing', 'done', 'failed')),
  requested_by uuid references auth.users(id) on delete set null,
  requested_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  priority integer not null default 0,
  result jsonb not null default '{}'::jsonb,
  error text
);

create index if not exists global_market_refresh_requests_status_idx
  on public.global_market_refresh_requests (status, priority desc, requested_at asc);

create table if not exists public.global_market_quotes (
  security text primary key,
  payload jsonb not null default '{}'::jsonb,
  fx numeric,
  source text,
  as_of text,
  updated_at timestamptz not null default now(),
  error text
);

alter table public.global_market_refresh_requests enable row level security;
alter table public.global_market_quotes enable row level security;

drop policy if exists "global market requests are readable by users"
  on public.global_market_refresh_requests;
create policy "global market requests are readable by users"
  on public.global_market_refresh_requests
  for select
  to authenticated
  using (true);

drop policy if exists "users can create global market requests"
  on public.global_market_refresh_requests;
create policy "users can create global market requests"
  on public.global_market_refresh_requests
  for insert
  to authenticated
  with check (requested_by is null or requested_by = (select auth.uid()));

drop policy if exists "global market quotes are readable by users"
  on public.global_market_quotes;
create policy "global market quotes are readable by users"
  on public.global_market_quotes
  for select
  to authenticated
  using (true);

revoke all on public.global_market_refresh_requests from anon;
revoke all on public.global_market_quotes from anon;
grant select, insert on public.global_market_refresh_requests to authenticated;
grant select on public.global_market_quotes to authenticated;
grant all on public.global_market_refresh_requests to service_role;
grant all on public.global_market_quotes to service_role;

do $$
begin
  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'global_market_refresh_requests'
  ) then
    alter publication supabase_realtime add table public.global_market_refresh_requests;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'global_market_quotes'
  ) then
    alter publication supabase_realtime add table public.global_market_quotes;
  end if;
end $$;
