-- QuantRAG schema. Idempotent: backend/ingest/run.py applies it on every run.
-- On Supabase the vector extension lives in the `extensions` schema, hence the search_path.
create extension if not exists vector;
create schema if not exists quantrag;
set search_path = quantrag, public, extensions;

create table if not exists companies (
  id serial primary key,
  symbol text unique not null,
  name text not null,
  sector text not null,
  aliases text[] not null default '{}'
);

create table if not exists documents (
  id serial primary key,
  company_id int not null references companies,
  fiscal_label text not null,
  period_end date not null,
  call_date date not null,
  source_url text not null,
  sha256 text unique not null,
  ingested_at timestamptz default now(),
  unique (company_id, fiscal_label)
);

create table if not exists chunks (
  id bigserial primary key,
  document_id int not null references documents on delete cascade,
  speaker text,
  role text check (role in ('management', 'analyst', 'moderator', 'unknown')),
  section text check (section in ('prepared', 'qa', 'unknown')),
  page int,
  text text not null,
  tsv tsvector generated always as (to_tsvector('english', text)) stored,
  embedding vector(384)
);
create index if not exists chunks_embedding_idx on chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_tsv_idx on chunks using gin (tsv);
create index if not exists chunks_document_idx on chunks (document_id);

create table if not exists chunk_numbers (
  chunk_id bigint not null references chunks on delete cascade,
  raw text not null,
  value double precision not null,
  unit text,
  scale text
);
create index if not exists chunk_numbers_chunk_idx on chunk_numbers (chunk_id);

create table if not exists eval_runs (
  id serial primary key,
  git_sha text,
  created_at timestamptz default now(),
  metrics jsonb
);
