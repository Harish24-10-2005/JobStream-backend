-- Create user_network_leads table for persisting Network Agent results
create table if not exists public.user_network_leads (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references public.user_profiles(user_id) on delete cascade not null,
    
    -- Connection Details
    name text not null,
    headline text not null,
    company text not null,
    profile_url text not null,
    
    -- How we found them
    connection_type text not null, -- 'alumni', 'location', 'company', 'mutual'
    match_detail text, -- 'Stanford University', 'San Francisco', 'Google'
    confidence_score float default 0.0,
    
    -- AI Generated Content
    outreach_draft text,
    
    -- Metadata
    created_at timestamptz default now(),
    is_contacted boolean default false,
    notes text
);

-- Enable RLS
alter table public.user_network_leads enable row level security;

-- Policy: Users can view their own leads
create policy "Users can view own leads"
on public.user_network_leads for select
using (auth.uid() = user_id);

-- Policy: Users can insert their own leads
create policy "Users can insert own leads"
on public.user_network_leads for insert
with check (auth.uid() = user_id);

-- Policy: Users can update their own leads
create policy "Users can update own leads"
on public.user_network_leads for update
using (auth.uid() = user_id);

-- Policy: Users can delete their own leads
create policy "Users can delete own leads"
on public.user_network_leads for delete
using (auth.uid() = user_id);
