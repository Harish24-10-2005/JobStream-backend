-- ====================================================================================
-- 07_all_missing_tables.sql
-- Consolidated migration: Creates ALL missing tables required by the backend.
-- Safe to run multiple times (uses IF NOT EXISTS).
-- ====================================================================================

-- ============================================================
-- 1. resume_templates — LaTeX resume templates for generation
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resume_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    latex_template TEXT NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    preview_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.resume_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Resume templates are viewable by all authenticated users"
    ON public.resume_templates FOR SELECT
    USING (auth.role() = 'authenticated');

-- Seed a default ATS template placeholder (update latex_template with your actual template)
INSERT INTO public.resume_templates (name, description, latex_template, is_default)
SELECT 'ATS Classic', 'Clean ATS-optimized single-column resume', '% REPLACE WITH YOUR LATEX TEMPLATE', TRUE
WHERE NOT EXISTS (SELECT 1 FROM public.resume_templates WHERE is_default = TRUE);


-- ============================================================
-- 2. platform_credentials — Encrypted job platform credentials
-- ============================================================
CREATE TABLE IF NOT EXISTS public.platform_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    credential_type TEXT DEFAULT 'password',
    encrypted_username TEXT NOT NULL,
    encrypted_password TEXT NOT NULL,
    encryption_iv TEXT NOT NULL,
    is_valid BOOLEAN DEFAULT TRUE,
    last_used TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, platform)
);

ALTER TABLE public.platform_credentials ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own credentials"
    ON public.platform_credentials FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ============================================================
-- 3. job_searches — Job search history tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS public.job_searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    location TEXT,
    platforms TEXT[] DEFAULT ARRAY['greenhouse', 'lever', 'ashby'],
    result_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_searches_user_id ON public.job_searches(user_id);

ALTER TABLE public.job_searches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own job searches"
    ON public.job_searches FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ============================================================
-- 4. user_network_leads — Network Agent results
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_network_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.user_profiles(user_id) ON DELETE CASCADE NOT NULL,
    name TEXT NOT NULL,
    headline TEXT NOT NULL,
    company TEXT NOT NULL,
    profile_url TEXT NOT NULL,
    connection_type TEXT NOT NULL,       -- 'alumni', 'location', 'company', 'mutual'
    match_detail TEXT,                    -- 'Stanford University', 'San Francisco', etc.
    confidence_score FLOAT DEFAULT 0.0,
    outreach_draft TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_contacted BOOLEAN DEFAULT FALSE,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_user_network_leads_user_id ON public.user_network_leads(user_id);

ALTER TABLE public.user_network_leads ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own leads"
    ON public.user_network_leads FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own leads"
    ON public.user_network_leads FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own leads"
    ON public.user_network_leads FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own leads"
    ON public.user_network_leads FOR DELETE
    USING (auth.uid() = user_id);


-- ============================================================
-- 5. user_company_reports — Company Agent "Insider Dossiers"
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_company_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.user_profiles(user_id) ON DELETE CASCADE NOT NULL,
    company_name TEXT NOT NULL,
    report_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_user_company_reports_user_id ON public.user_company_reports(user_id);

ALTER TABLE public.user_company_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own reports"
    ON public.user_company_reports FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own reports"
    ON public.user_company_reports FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own reports"
    ON public.user_company_reports FOR DELETE
    USING (auth.uid() = user_id);


-- ============================================================
-- 6. user_interview_sessions — Mock Interview sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.user_profiles(user_id) ON DELETE CASCADE NOT NULL,
    role TEXT NOT NULL,
    company TEXT,
    persona TEXT NOT NULL,
    status TEXT DEFAULT 'active',          -- active, completed, abandoned
    feedback_summary JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_interview_sessions_user_id ON public.user_interview_sessions(user_id);

ALTER TABLE public.user_interview_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own sessions"
    ON public.user_interview_sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own sessions"
    ON public.user_interview_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own sessions"
    ON public.user_interview_sessions FOR UPDATE
    USING (auth.uid() = user_id);


-- ============================================================
-- 7. user_interview_messages — Interview chat history
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_interview_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES public.user_interview_sessions(id) ON DELETE CASCADE NOT NULL,
    role TEXT NOT NULL,                    -- 'user' or 'ai'
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_interview_messages_session_id ON public.user_interview_messages(session_id);

ALTER TABLE public.user_interview_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own messages"
    ON public.user_interview_messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.user_interview_sessions
            WHERE id = user_interview_messages.session_id
            AND user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert own messages"
    ON public.user_interview_messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.user_interview_sessions
            WHERE id = user_interview_messages.session_id
            AND user_id = auth.uid()
        )
    );


-- ============================================================
-- 8. user_salary_battles — Salary negotiation sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_salary_battles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.user_profiles(user_id) ON DELETE CASCADE NOT NULL,
    role TEXT NOT NULL,
    company TEXT,
    location TEXT,
    initial_offer INT NOT NULL,
    current_offer INT,
    target_salary INT,
    difficulty TEXT DEFAULT 'medium',       -- easy, medium, hard
    status TEXT DEFAULT 'active',           -- active, won, lost, abandoned
    round_count INT DEFAULT 0,
    feedback JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_salary_battles_user_id ON public.user_salary_battles(user_id);

ALTER TABLE public.user_salary_battles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own battles"
    ON public.user_salary_battles FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own battles"
    ON public.user_salary_battles FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own battles"
    ON public.user_salary_battles FOR UPDATE
    USING (auth.uid() = user_id);


-- ============================================================
-- 9. user_salary_messages — Salary negotiation chat history
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_salary_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    battle_id UUID REFERENCES public.user_salary_battles(id) ON DELETE CASCADE NOT NULL,
    role TEXT NOT NULL,                    -- 'user', 'ai', 'system'
    content TEXT NOT NULL,
    offer_amount INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_salary_messages_battle_id ON public.user_salary_messages(battle_id);

ALTER TABLE public.user_salary_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own battle messages"
    ON public.user_salary_messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.user_salary_battles
            WHERE id = user_salary_messages.battle_id
            AND user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert own battle messages"
    ON public.user_salary_messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.user_salary_battles
            WHERE id = user_salary_messages.battle_id
            AND user_id = auth.uid()
        )
    );


-- ============================================================
-- 10. user_generated_resumes — AI-tailored resumes
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_generated_resumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_title TEXT,
    company_name TEXT,
    job_url TEXT,
    tailored_content JSONB,
    latex_source TEXT,
    pdf_path TEXT,
    pdf_url TEXT,
    ats_score INTEGER,
    match_score INTEGER,
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, NOW()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_generated_resumes_user_id ON public.user_generated_resumes(user_id);

ALTER TABLE public.user_generated_resumes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own generated resumes"
    ON public.user_generated_resumes FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own generated resumes"
    ON public.user_generated_resumes FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own generated resumes"
    ON public.user_generated_resumes FOR DELETE
    USING (auth.uid() = user_id);


-- ============================================================
-- 11. user_cover_letters — Generated cover letters
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_cover_letters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    resume_id UUID REFERENCES public.user_generated_resumes(id),
    job_title TEXT,
    company_name TEXT,
    job_url TEXT,
    content JSONB,
    final_text TEXT,
    tone TEXT,
    pdf_path TEXT,
    pdf_url TEXT,
    created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, NOW()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_cover_letters_user_id ON public.user_cover_letters(user_id);

ALTER TABLE public.user_cover_letters ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own cover letters"
    ON public.user_cover_letters FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own cover letters"
    ON public.user_cover_letters FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own cover letters"
    ON public.user_cover_letters FOR DELETE
    USING (auth.uid() = user_id);


-- ============================================================
-- DONE — All 11 missing tables created
-- ============================================================
