create table if not exists public.stock_market_master (
  code text primary key check (code ~ '^[0-9]{6}$'),
  market text not null check (market in ('코스피', '코스닥')),
  source text not null default 'kiwoom',
  updated_at timestamptz not null default now()
);

create index if not exists stock_market_master_market_idx
  on public.stock_market_master (market, code);

alter table public.stock_market_master enable row level security;

drop policy if exists "approved users read stock market master"
  on public.stock_market_master;
create policy "approved users read stock market master"
  on public.stock_market_master for select to authenticated
  using (private.is_approved_user());

revoke all on public.stock_market_master from anon, authenticated;
grant select on public.stock_market_master to authenticated;
grant select, insert, update, delete on public.stock_market_master to service_role;

comment on table public.stock_market_master is
  'Stable KOSPI/KOSDAQ membership by stock code. Refreshed manually when the listed universe changes.';

update storage.buckets
set file_size_limit = 10485760
where id = 'dashboard-live'
  and coalesce(file_size_limit, 0) < 10485760;
