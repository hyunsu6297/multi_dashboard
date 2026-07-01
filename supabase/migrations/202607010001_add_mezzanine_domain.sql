alter table public.manual_file_rows
  drop constraint if exists manual_file_rows_domain_check;

alter table public.manual_file_rows
  add constraint manual_file_rows_domain_check
  check (domain in ('stock', 'bond', 'mezzanine', 'fund'));

alter table app.dashboard_cards
  drop constraint if exists dashboard_cards_section_check;

alter table app.dashboard_cards
  add constraint dashboard_cards_section_check
  check (section in ('overview', 'stock', 'bond', 'mezzanine', 'fund', 'etf'));

grant select, insert, update, delete on table public.manual_file_rows to authenticated;
grant select, insert, update, delete on table public.manual_file_rows to service_role;
revoke all on table public.manual_file_rows from anon;
alter table public.manual_file_rows enable row level security;

