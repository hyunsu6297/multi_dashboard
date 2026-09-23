create table if not exists public.stock_performance_snapshots (
  id bigint generated always as identity primary key,
  performance_date date not null,
  holdings_snapshot_date date,
  fund_scope text not null check (char_length(fund_scope) between 1 and 200),
  captured_at timestamptz not null,
  environment text not null default 'local_test'
    check (environment in ('local_test', 'production')),
  calculation_version text not null default 'v1'
    check (char_length(calculation_version) between 1 and 50),
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (performance_date, fund_scope, environment)
);

create index if not exists stock_performance_snapshots_period_idx
  on public.stock_performance_snapshots (environment, fund_scope, performance_date);

alter table public.stock_performance_snapshots enable row level security;

drop policy if exists "approved users read stock performance snapshots"
  on public.stock_performance_snapshots;
create policy "approved users read stock performance snapshots"
  on public.stock_performance_snapshots for select to authenticated
  using (private.is_approved_user());

revoke all on public.stock_performance_snapshots from anon, authenticated;
grant select on public.stock_performance_snapshots to authenticated;
grant select, insert, update on public.stock_performance_snapshots to service_role;

comment on table public.stock_performance_snapshots is
  'Daily immutable-in-shape stock performance payloads for period analysis; local testing is isolated by environment.';
