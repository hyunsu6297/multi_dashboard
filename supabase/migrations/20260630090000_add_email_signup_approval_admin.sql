alter table public.user_profiles
  add column if not exists email text,
  add column if not exists status text not null default 'pending',
  add column if not exists approved_at timestamptz,
  add column if not exists approved_by uuid references auth.users(id);

update public.user_profiles profile
set email = lower(auth_user.email),
    status = 'approved',
    approved_at = coalesce(profile.approved_at, profile.created_at)
from auth.users auth_user
where auth_user.id = profile.user_id;

alter table public.user_profiles
  drop constraint if exists user_profiles_status_check;
alter table public.user_profiles
  add constraint user_profiles_status_check
  check (status in ('pending', 'approved', 'rejected', 'suspended'));

create unique index if not exists user_profiles_email_lower_idx
  on public.user_profiles (lower(email))
  where email is not null;

create or replace function private.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.user_profiles (
    user_id,
    username,
    email,
    role,
    must_change_password,
    status
  )
  values (
    new.id,
    lower(new.email),
    lower(new.email),
    'viewer',
    false,
    'pending'
  )
  on conflict (user_id) do nothing;
  return new;
end;
$$;

revoke all on function private.handle_new_auth_user() from public;
grant execute on function private.handle_new_auth_user() to supabase_auth_admin;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function private.handle_new_auth_user();

create or replace function private.is_approved_user()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.user_profiles profile
    where profile.user_id = (select auth.uid())
      and profile.status = 'approved'
      and profile.must_change_password = false
  );
$$;

revoke all on function private.is_approved_user() from public;
grant execute on function private.is_approved_user() to authenticated, service_role;

drop policy if exists "users complete password change" on public.user_profiles;
drop policy if exists "admins read all profiles" on public.user_profiles;
drop policy if exists "admins update profiles" on public.user_profiles;

create policy "admins read all profiles"
  on public.user_profiles for select to authenticated
  using (private.has_app_role(array['admin']));

create policy "admins update profiles"
  on public.user_profiles for update to authenticated
  using (private.has_app_role(array['admin']))
  with check (private.has_app_role(array['admin']));

revoke insert, update, delete on public.user_profiles from authenticated;
grant select on public.user_profiles to authenticated;
grant update (role, status, approved_at, approved_by, updated_at)
  on public.user_profiles to authenticated;

drop policy if exists "read manual file rows" on public.manual_file_rows;
drop policy if exists "insert manual file rows" on public.manual_file_rows;
drop policy if exists "update manual file rows" on public.manual_file_rows;
drop policy if exists "delete manual file rows" on public.manual_file_rows;

create policy "read manual file rows"
  on public.manual_file_rows for select to authenticated
  using (private.is_approved_user());
create policy "insert manual file rows"
  on public.manual_file_rows for insert to authenticated
  with check (
    private.is_approved_user()
    and private.has_app_role(array['admin', 'editor'])
  );
create policy "update manual file rows"
  on public.manual_file_rows for update to authenticated
  using (
    private.is_approved_user()
    and private.has_app_role(array['admin', 'editor'])
  )
  with check (
    private.is_approved_user()
    and private.has_app_role(array['admin', 'editor'])
  );
create policy "delete manual file rows"
  on public.manual_file_rows for delete to authenticated
  using (
    private.is_approved_user()
    and private.has_app_role(array['admin', 'editor'])
  );

drop policy if exists "authenticated users read KFR snapshots" on public.kfr_source_snapshots;
create policy "authenticated users read KFR snapshots"
  on public.kfr_source_snapshots for select to authenticated
  using (private.is_approved_user());

drop policy if exists "authenticated users read KFR rows" on public.kfr_source_rows;
create policy "authenticated users read KFR rows"
  on public.kfr_source_rows for select to authenticated
  using (private.is_approved_user());

drop policy if exists "authenticated users read realtime quotes" on public.kiwoom_realtime_quotes;
create policy "authenticated users read realtime quotes"
  on public.kiwoom_realtime_quotes for select to authenticated
  using (private.is_approved_user());

drop policy if exists "authenticated users read live dashboard versions" on public.dashboard_live_versions;
create policy "authenticated users read live dashboard versions"
  on public.dashboard_live_versions for select to authenticated
  using (private.is_approved_user());

drop policy if exists "authenticated users read live dashboards" on storage.objects;
create policy "authenticated users read live dashboards"
  on storage.objects for select to authenticated
  using (bucket_id = 'dashboard-live' and private.is_approved_user());
