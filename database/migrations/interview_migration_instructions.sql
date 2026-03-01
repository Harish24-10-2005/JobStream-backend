-- ====================================================================================
-- INTERVIEW AGENT MIGRATION INSTRUCTIONS
-- ====================================================================================

-- 1. Open your Supabase SQL Editor: https://supabase.com/dashboard/project/_/sql/new
-- 2. Copy and paste the content below.
-- 3. Click "Run" to create the session tables.

-- Create user_interview_sessions table
create table if not exists public.user_interview_sessions (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references public.user_profiles(user_id) on delete cascade not null,
    
    role text not null,        -- e.g. "Senior Python Dev"
    company text,              -- e.g. "Google"
    persona text not null,     -- e.g. "Grumpy CTO"
    
    status text default 'active', -- active, completed, abandoned
    
    feedback_summary jsonb,    -- Final feedback from the AI
    
    created_at timestamptz default now()
);

-- Create user_interview_messages table (The Chat History)
create table if not exists public.user_interview_messages (
    id uuid default gen_random_uuid() primary key,
    session_id uuid references public.user_interview_sessions(id) on delete cascade not null,
    
    role text not null,        -- 'user' or 'ai'
    content text not null,     -- The actual message
    
    created_at timestamptz default now()
);

-- Enable RLS
alter table public.user_interview_sessions enable row level security;
alter table public.user_interview_messages enable row level security;

-- Policies for Sessions
create policy "Users can view own sessions"
on public.user_interview_sessions for select
using (auth.uid() = user_id);

create policy "Users can insert own sessions"
on public.user_interview_sessions for insert
with check (auth.uid() = user_id);

create policy "Users can update own sessions"
on public.user_interview_sessions for update
using (auth.uid() = user_id);

-- Policies for Messages
create policy "Users can view own messages"
on public.user_interview_messages for select
using (
    exists (
        select 1 from public.user_interview_sessions
        where id = user_interview_messages.session_id
        and user_id = auth.uid()
    )
);

create policy "Users can insert own messages"
on public.user_interview_messages for insert
with check (
    exists (
        select 1 from public.user_interview_sessions
        where id = user_interview_messages.session_id
        and user_id = auth.uid()
    )
);
