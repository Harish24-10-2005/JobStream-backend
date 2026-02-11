-- Migration: Add discovered_jobs table
-- Required by: ScoutAgent, AnalystAgent, db_service.py
-- Run this in Supabase SQL Editor if the table doesn't exist yet

CREATE TABLE IF NOT EXISTS discovered_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Job Details
    title TEXT,
    company TEXT,
    location TEXT,
    url TEXT NOT NULL,
    source TEXT,
    
    -- Analysis Results  
    match_score INTEGER,
    tech_stack TEXT[],
    analysis JSONB DEFAULT '{}'::JSONB,
    
    -- Status
    status TEXT DEFAULT 'discovered',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_discovered_jobs_user_id ON discovered_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_discovered_jobs_status ON discovered_jobs(user_id, status);
CREATE INDEX IF NOT EXISTS idx_discovered_jobs_score ON discovered_jobs(match_score);

-- RLS
ALTER TABLE discovered_jobs ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'discovered_jobs' AND policyname = 'Users can manage own discovered jobs'
    ) THEN
        CREATE POLICY "Users can manage own discovered jobs" ON discovered_jobs
            FOR ALL USING (auth.uid() = user_id);
    END IF;
END $$;

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_discovered_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_discovered_jobs_updated_at ON discovered_jobs;
CREATE TRIGGER trigger_discovered_jobs_updated_at
    BEFORE UPDATE ON discovered_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_discovered_jobs_updated_at();
