create table if not exists public.clips (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  project_id text not null,
  project_name text not null,
  
  -- This idek if we need it rn lowkey
  source text not null default 'ai' check (source in ('ai', 'suit', 'review')),
  duration text not null default '0:00',
  file_path text not null,
  created_at timestamptz not null default now()
);

alter table public.clips enable row level security;

create policy "anyone can list clips" on public.clips for select to anon, authenticated using (true);
create policy "anyone can add clips" on public.clips for insert to anon, authenticated with check (true);

insert into storage.buckets (id, name, public)
values ('clips', 'clips', true)
on conflict (id) do nothing;

create policy "anyone can upload clip files" on storage.objects for insert to anon, authenticated
  with check (bucket_id = 'clips');
