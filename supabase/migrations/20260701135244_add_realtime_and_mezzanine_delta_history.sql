create table if not exists public.mezzanine_delta_history (
  business_date date not null,
  security_code text not null,
  security_name text not null default '',
  fund_name text not null default '',
  nav numeric not null,
  nav_return numeric,
  underlying_change_rate numeric,
  daily_delta numeric,
  is_valid boolean not null default false,
  source text not null check (source in ('historical_xlsx', 'kfr_daily')),
  source_snapshot_id bigint references public.kfr_source_snapshots(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (business_date, security_code, fund_name)
);

create index if not exists mezzanine_delta_history_security_date_idx
  on public.mezzanine_delta_history (security_code, business_date desc);

alter table public.mezzanine_delta_history enable row level security;

drop policy if exists "approved users read mezzanine delta history"
  on public.mezzanine_delta_history;
create policy "approved users read mezzanine delta history"
  on public.mezzanine_delta_history for select to authenticated
  using (private.is_approved_user());

revoke all on public.mezzanine_delta_history from anon, authenticated;
grant select on public.mezzanine_delta_history to authenticated;
grant select, insert, update, delete on public.mezzanine_delta_history to service_role;

do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'manual_file_rows'
  ) then
    alter publication supabase_realtime add table public.manual_file_rows;
  end if;

  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'mezzanine_delta_history'
  ) then
    alter publication supabase_realtime add table public.mezzanine_delta_history;
  end if;
end;
$$;
