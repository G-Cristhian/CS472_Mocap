create table if not exists public.footage (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  file_path text not null,
  size_bytes bigint not null,
  take_id text,
  project_id text,
  created_at timestamptz not null default now()
);

alter table public.footage enable row level security;

create policy "anyone can list footage" on public.footage for select to anon, authenticated using (true);
create policy "anyone can add footage" on public.footage for insert to anon, authenticated with check (true);
create policy "anyone can mark footage processed" on public.footage for update to anon, authenticated
  using (true) with check (true);
revoke update on public.footage from anon, authenticated;
grant update (take_id, project_id) on public.footage to anon, authenticated;

insert into storage.buckets (id, name, public)
values ('footage', 'footage', true)
on conflict (id) do nothing;

create policy "anyone can upload footage files" on storage.objects for insert to anon, authenticated
  with check (bucket_id = 'footage');
