-- ====================================================================================
-- SALARY NEGOTIATION BATTLE TABLES
-- ====================================================================================

-- 1. Table: user_salary_battles
create table if not exists public.user_salary_battles (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references public.user_profiles(user_id) on delete cascade not null,
    
    role text not null,          -- e.g. "Senior Frontend Dev"
    company text,                -- e.g. "Startup Inc"
    location text,               -- e.g. "Remote"
    
    initial_offer int not null,  -- e.g. 120000
    current_offer int,           -- Tracks the latest offer on table
    target_salary int,           -- User's goal
    
    difficulty text default 'medium', -- easy, medium, hard (affects AI stubbornness)
    status text default 'active',  -- active, won, lost, abandoned
    
    round_count int default 0,
    
    feedback jsonb,              -- Final analysis
    
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- 2. Table: user_salary_messages
create table if not exists public.user_salary_messages (
    id uuid default gen_random_uuid() primary key,
    battle_id uuid references public.user_salary_battles(id) on delete cascade not null,
    
    role text not null,          -- 'user', 'ai', 'system'
    content text not null,
    
    offer_amount int,            -- If a number was proposed in this turn
    
    created_at timestamptz default now()
);

-- 3. RLS Policies
alter table public.user_salary_battles enable row level security;
alter table public.user_salary_messages enable row level security;

-- Battles
create policy "Users can view own battles"
on public.user_salary_battles for select
using (auth.uid() = user_id);

create policy "Users can insert own battles"
on public.user_salary_battles for insert
with check (auth.uid() = user_id);

create policy "Users can update own battles"
on public.user_salary_battles for update
using (auth.uid() = user_id);

-- Messages
create policy "Users can view own battle messages"
on public.user_salary_messages for select
using (
    exists (
        select 1 from public.user_salary_battles
        where id = user_salary_messages.battle_id
        and user_id = auth.uid()
    )
);

create policy "Users can insert own battle messages"
on public.user_salary_messages for insert
with check (
    exists (
        select 1 from public.user_salary_battles
        where id = user_salary_messages.battle_id
        and user_id = auth.uid()
    )
);
