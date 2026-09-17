create table if not exists public.stock_performance_ai_results (
  as_of_date date not null,
  selected_fund text not null check (char_length(selected_fund) between 1 and 200),
  holdings_snapshot_date date,
  analysis text not null check (char_length(analysis) between 1 and 20000),
  model text not null,
  usage jsonb not null default '{}'::jsonb,
  generated_at timestamptz not null default now(),
  generated_by uuid references auth.users (id) on delete set null,
  primary key (as_of_date, selected_fund)
);

create index if not exists stock_performance_ai_results_generated_idx
  on public.stock_performance_ai_results (generated_at desc);

alter table public.stock_performance_ai_results enable row level security;

drop policy if exists "approved users read stock performance AI results"
  on public.stock_performance_ai_results;
create policy "approved users read stock performance AI results"
  on public.stock_performance_ai_results for select to authenticated
  using (private.is_approved_user());

revoke all on public.stock_performance_ai_results from anon, authenticated;
grant select on public.stock_performance_ai_results to authenticated;
grant select, insert, update, delete on public.stock_performance_ai_results to service_role;

comment on table public.stock_performance_ai_results is
  'Latest shared AI performance analysis by analysis date and selected fund.';
