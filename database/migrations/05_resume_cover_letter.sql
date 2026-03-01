-- 05_resume_cover_letter.sql
-- Migration for Resume and Cover Letter Persistence + RAG

-- 1. Create table for Original/Base Resumes
create table if not exists public.user_resumes (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references auth.users(id) not null,
    name text not null default 'Primary Resume',
    file_path text not null, -- Supabase Storage path
    file_url text, -- Public URL
    file_type text default 'application/pdf',
    file_size bigint,
    is_primary boolean default false,
    content_embedding vector(768), -- Google Gecko embedding (768 dim)
    full_text text, -- Extracted text for RAG
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- 2. Create table for Generated (Tailored) Resumes
create table if not exists public.user_generated_resumes (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references auth.users(id) not null,
    job_title text,
    company_name text,
    job_url text,
    
    -- Content
    tailored_content jsonb, -- The full JSON structure used to generate PDF
    latex_source text, -- For re-compilation/editing
    
    -- Output
    pdf_path text,
    pdf_url text,
    
    -- Scores
    ats_score integer,
    match_score integer,
    
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- 3. Create table for Generated Cover Letters
create table if not exists public.user_cover_letters (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references auth.users(id) not null,
    resume_id uuid references public.user_generated_resumes(id), -- Optional link to specific resume
    
    job_title text,
    company_name text,
    job_url text,
    
    -- Content
    content jsonb, -- The structured content (paragraphs)
    final_text text, -- The full compiled text
    tone text, -- professional, enthusiastic, etc.
    
    -- Output
    pdf_path text,
    pdf_url text,
    
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- 4. Enable RLS
alter table public.user_resumes enable row level security;
alter table public.user_generated_resumes enable row level security;
alter table public.user_cover_letters enable row level security;

-- 5. RLS Policies
-- user_resumes
create policy "Users can view their own resumes"
    on public.user_resumes for select
    using (auth.uid() = user_id);

create policy "Users can insert their own resumes"
    on public.user_resumes for insert
    with check (auth.uid() = user_id);

create policy "Users can update their own resumes"
    on public.user_resumes for update
    using (auth.uid() = user_id);

create policy "Users can delete their own resumes"
    on public.user_resumes for delete
    using (auth.uid() = user_id);

-- user_generated_resumes
create policy "Users can view their own generated resumes"
    on public.user_generated_resumes for select
    using (auth.uid() = user_id);

create policy "Users can insert their own generated resumes"
    on public.user_generated_resumes for insert
    with check (auth.uid() = user_id);

-- user_cover_letters
create policy "Users can view their own cover letters"
    on public.user_cover_letters for select
    using (auth.uid() = user_id);

create policy "Users can insert their own cover letters"
    on public.user_cover_letters for insert
    with check (auth.uid() = user_id);
