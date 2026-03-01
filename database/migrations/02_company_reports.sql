-- Create user_company_reports table for persisting Company Agent "Insider Dossiers"
create table if not exists public.user_company_reports (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references public.user_profiles(user_id) on delete cascade not null,
    
    company_name text not null,
    
    -- Store the full JSON analysis here (Company Info, Culture, Red Flags, Insights)
    report_data jsonb not null,
    
    created_at timestamptz default now(),
    notes text
);

-- Enable RLS
alter table public.user_company_reports enable row level security;

-- Policy: Users can view their own reports
create policy "Users can view own reports"
on public.user_company_reports for select
using (auth.uid() = user_id);

-- Policy: Users can insert their own reports
create policy "Users can insert own reports"
on public.user_company_reports for insert
with check (auth.uid() = user_id);

-- Policy: Users can delete their own reports
create policy "Users can delete own reports"
on public.user_company_reports for delete
using (auth.uid() = user_id);
