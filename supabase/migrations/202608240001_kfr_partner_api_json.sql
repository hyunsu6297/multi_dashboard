alter table public.kfr_source_snapshots
  drop constraint if exists kfr_source_snapshots_source_key_check;

alter table public.kfr_source_snapshots
  add constraint kfr_source_snapshots_source_key_check
  check (source_key in ('fund_prices', 'mezzanine_price', 'fund_trades', 'fund_holdings'));

alter table public.kfr_source_snapshots
  add column if not exists source_format text not null default 'excel',
  add column if not exists response_metadata jsonb not null default '{}'::jsonb;

comment on column public.kfr_source_snapshots.source_format is
  'Source representation. New KFR snapshots use kfr_partner_api_json.';

comment on column public.kfr_source_snapshots.response_metadata is
  'Top-level KFR API response fields excluding content.';
