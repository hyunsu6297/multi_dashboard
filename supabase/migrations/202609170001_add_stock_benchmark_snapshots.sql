create table if not exists public.stock_benchmark_snapshots (
  market text not null check (market in ('코스피', '코스닥')),
  business_date date not null,
  source_date date not null,
  label text not null,
  source_url text not null,
  scale numeric not null check (scale > 0 and scale <= 1),
  row_count integer not null check (row_count >= 100),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  weights jsonb not null,
  downloaded_at timestamptz not null default now(),
  primary key (market, business_date)
);

create index if not exists stock_benchmark_snapshots_latest_idx
  on public.stock_benchmark_snapshots (business_date desc, market);

alter table public.stock_benchmark_snapshots enable row level security;

drop policy if exists "approved users read stock benchmarks"
  on public.stock_benchmark_snapshots;
create policy "approved users read stock benchmarks"
  on public.stock_benchmark_snapshots for select to authenticated
  using (private.is_approved_user());

revoke all on public.stock_benchmark_snapshots from anon, authenticated;
grant select on public.stock_benchmark_snapshots to authenticated;
grant select, insert, update, delete on public.stock_benchmark_snapshots to service_role;

comment on table public.stock_benchmark_snapshots is
  'Daily KODEX KOSPI and KODEX KOSDAQ150 benchmark constituent weights used by the stock dashboard.';
