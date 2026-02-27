-- ============================================================
-- Phase 1 Migration: Agent Intelligence & Observability Tables
-- Apply via Supabase SQL Editor or migration tool
-- ============================================================

-- 1. Agent Memories — persistent memory for AI agents
CREATE TABLE IF NOT EXISTS agent_memories (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    memory_key TEXT NOT NULL,
    memory_value TEXT NOT NULL,
    memory_type TEXT NOT NULL DEFAULT 'context',
    confidence FLOAT DEFAULT 1.0,
    access_count INTEGER DEFAULT 0,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, agent_name, memory_key)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_agent_memories_agent_user
    ON agent_memories(agent_name, user_id);
CREATE INDEX IF NOT EXISTS idx_agent_memories_type
    ON agent_memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_agent_memories_expires
    ON agent_memories(expires_at) WHERE expires_at IS NOT NULL;

-- RLS
ALTER TABLE agent_memories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own agent memories"
    ON agent_memories FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- 2. Agent Feedback — user ratings for agent outputs
CREATE TABLE IF NOT EXISTS agent_feedback (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    session_id TEXT,
    rating FLOAT NOT NULL CHECK (rating >= 1.0 AND rating <= 5.0),
    comments TEXT DEFAULT '',
    context JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_feedback_agent
    ON agent_feedback(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_user
    ON agent_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_rating
    ON agent_feedback(agent_name, rating);

ALTER TABLE agent_feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own feedback"
    ON agent_feedback FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- 3. LLM Costs — token usage and spend tracking
CREATE TABLE IF NOT EXISTS llm_costs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd FLOAT NOT NULL DEFAULT 0,
    session_id TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_costs_agent
    ON llm_costs(agent_name);
CREATE INDEX IF NOT EXISTS idx_llm_costs_date
    ON llm_costs(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_costs_model
    ON llm_costs(model);

-- No RLS on llm_costs — this is system-level data
-- Access controlled via service role key only
ALTER TABLE llm_costs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role only for llm_costs"
    ON llm_costs FOR ALL
    USING (auth.role() = 'service_role');


-- 4. User Skills — skill tracking for gap analysis
CREATE TABLE IF NOT EXISTS user_skills (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    skill_name TEXT NOT NULL,
    proficiency TEXT DEFAULT 'intermediate',
    source TEXT DEFAULT 'self_reported',
    verified BOOLEAN DEFAULT FALSE,
    endorsed_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, skill_name)
);

CREATE INDEX IF NOT EXISTS idx_user_skills_user
    ON user_skills(user_id);
CREATE INDEX IF NOT EXISTS idx_user_skills_name
    ON user_skills(skill_name);

ALTER TABLE user_skills ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own skills"
    ON user_skills FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- 5. Updated_at trigger for auto-updating timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_agent_memories_updated_at
    BEFORE UPDATE ON agent_memories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_skills_updated_at
    BEFORE UPDATE ON user_skills
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
