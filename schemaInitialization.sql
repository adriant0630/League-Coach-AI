-- Run this in the Supabase SQL Editor (Dashboard -> SQL Editor -> New Query)

-- 1. Enable the pgvector extension
create extension if not exists vector;

-- 2. Table to store our knowledge chunks
-- embedding dimension is 384 because we're using all-MiniLM-L6-v2,
-- which outputs 384-dimensional vectors. If you switch embedding models,
-- you MUST update this number to match that model's output size.
create table champion_chunks (
    id bigserial primary key,
    champion text not null,
    section text not null,        -- e.g. 'playing_as', 'playing_against', 'countering', 'item_usage'
    content text not null,        -- the cleaned text chunk
    embedding vector(384),        -- the embedding vector for this chunk
    created_at timestamptz default now()
);

-- 3. Index for fast similarity search (cosine distance)
-- this makes retrieval fast even as your corpus grows
create index on champion_chunks using hnsw (embedding vector_cosine_ops);

-- 4. A helper function to do similarity search from our backend
-- returns the top N most similar chunks to a given query embedding
create or replace function match_chunks (
    query_embedding vector(384),
    match_count int default 5,
    filter_champion text default null
)
returns table (
    id bigint,
    champion text,
    section text,
    content text,
    similarity float
)
language sql stable
as $$
    select
        champion_chunks.id,
        champion_chunks.champion,
        champion_chunks.section,
        champion_chunks.content,
        1 - (champion_chunks.embedding <=> query_embedding) as similarity
    from champion_chunks
    where filter_champion is null or champion_chunks.champion = filter_champion
    order by champion_chunks.embedding <=> query_embedding
    limit match_count;
$$;