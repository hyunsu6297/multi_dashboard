create table if not exists public.kiwoom_daily_prices (
  business_date date not null,
  code text not null,
  name text not null default '',
  close_price numeric not null,
  change_rate numeric,
  source text not null check (source in ('ka10081', 'ka10095')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (business_date, code)
);

create index if not exists kiwoom_daily_prices_code_date_idx
  on public.kiwoom_daily_prices (code, business_date desc);

alter table public.kiwoom_daily_prices enable row level security;

drop policy if exists "approved users read Kiwoom daily prices"
  on public.kiwoom_daily_prices;
create policy "approved users read Kiwoom daily prices"
  on public.kiwoom_daily_prices for select to authenticated
  using (private.is_approved_user());

revoke all on public.kiwoom_daily_prices from anon, authenticated;
grant select on public.kiwoom_daily_prices to authenticated;
grant select, insert, update, delete on public.kiwoom_daily_prices to service_role;
