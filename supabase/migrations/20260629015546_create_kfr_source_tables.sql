create table public.kfr_source_snapshots (
  id bigint generated always as identity primary key,
  source_key text not null check (source_key in ('mezzanine_price', 'fund_trades', 'fund_holdings')),
  business_date date not null,
  file_name text not null,
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  sheet_names jsonb not null default '[]'::jsonb,
  row_count integer not null check (row_count >= 0),
  downloaded_at timestamptz not null default now(),
  unique (source_key, business_date, sha256)
);

create table public.kfr_source_rows (
  snapshot_id bigint not null references public.kfr_source_snapshots(id) on delete cascade,
  sheet_name text not null,
  row_no integer not null check (row_no > 0),
  payload jsonb not null,
  primary key (snapshot_id, sheet_name, row_no)
);

create index kfr_source_snapshots_latest_idx
  on public.kfr_source_snapshots (source_key, business_date desc, downloaded_at desc);

create index kfr_source_rows_payload_gin_idx
  on public.kfr_source_rows using gin (payload jsonb_path_ops);

alter table public.kfr_source_snapshots enable row level security;
alter table public.kfr_source_rows enable row level security;

create policy "authenticated users read KFR snapshots"
  on public.kfr_source_snapshots for select to authenticated
  using (
    exists (
      select 1 from public.user_profiles profile
      where profile.user_id = (select auth.uid())
        and profile.must_change_password = false
    )
  );

create policy "authenticated users read KFR rows"
  on public.kfr_source_rows for select to authenticated
  using (
    exists (
      select 1 from public.user_profiles profile
      where profile.user_id = (select auth.uid())
        and profile.must_change_password = false
    )
  );

revoke all on public.kfr_source_snapshots from anon, authenticated;
revoke all on public.kfr_source_rows from anon, authenticated;
grant select on public.kfr_source_snapshots to authenticated;
grant select on public.kfr_source_rows to authenticated;

