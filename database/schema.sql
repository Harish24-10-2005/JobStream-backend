-- ============================================================================
-- JobAI Multi-User Database Schema for Supabase
-- Run this in your Supabase SQL Editor
-- ============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 1. USER PROFILES TABLE - Core user data
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Personal Information
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    full_name TEXT GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED,
    email TEXT NOT NULL,
    phone TEXT,
    
    -- Location
    city TEXT,
    country TEXT,
    address TEXT,
    
    -- URLs
    linkedin_url TEXT,
    github_url TEXT,
    portfolio_url TEXT,
    
    -- Demographics (optional)
    gender TEXT,
    veteran_status TEXT,
    disability_status TEXT,
    ethnicity TEXT,
    
    -- Application Preferences
    expected_salary TEXT,
    notice_period TEXT,
    work_authorization TEXT,
    relocation TEXT,
    employment_types TEXT[] DEFAULT ARRAY['Full-time'],
    
    -- Behavioral Questions (STAR format responses)
    behavioral_questions JSONB DEFAULT '{}',
    
    -- Skills as structured JSONB
    skills JSONB DEFAULT '{}',
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_user_profile UNIQUE (user_id)
);

-- ============================================================================
-- 2. USER EDUCATION TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_education (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    degree TEXT NOT NULL,
    major TEXT NOT NULL,
    university TEXT NOT NULL,
    cgpa TEXT,
    start_date DATE,
    end_date DATE,
    is_current BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 3. USER EXPERIENCE TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_experience (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    start_date DATE,
    end_date DATE,
    is_current BOOLEAN DEFAULT FALSE,
    description TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 4. USER PROJECTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    name TEXT NOT NULL,
    tech_stack TEXT[] DEFAULT ARRAY[]::TEXT[],
    description TEXT,
    project_url TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 5. USER RESUMES TABLE (stores resume files metadata)
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    name TEXT NOT NULL DEFAULT 'Primary Resume',
    file_path TEXT NOT NULL, -- Supabase Storage path
    file_url TEXT, -- Public URL if available
    file_type TEXT DEFAULT 'application/pdf',
    file_size INTEGER,
    
    is_primary BOOLEAN DEFAULT FALSE,
    
    -- Parsed content for quick access
    parsed_content JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 6. GENERATED RESUMES TABLE (AI-tailored resumes)
-- ============================================================================
CREATE TABLE IF NOT EXISTS generated_resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    base_resume_id UUID REFERENCES user_resumes(id),
    
    job_url TEXT,
    job_title TEXT,
    company_name TEXT,
    
    original_content JSONB DEFAULT '{}',
    tailored_content JSONB DEFAULT '{}',
    latex_source TEXT,
    
    -- Storage
    pdf_path TEXT, -- Supabase Storage path
    pdf_url TEXT,
    
    -- Scoring
    ats_score INTEGER,
    match_score INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 7. COVER LETTERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS cover_letters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    resume_id UUID REFERENCES generated_resumes(id),
    
    job_url TEXT,
    job_title TEXT,
    company_name TEXT,
    tone TEXT DEFAULT 'professional',
    
    content JSONB DEFAULT '{}',
    latex_source TEXT,
    pdf_path TEXT,
    pdf_url TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 8. JOB APPLICATIONS TRACKER
-- ============================================================================
CREATE TABLE IF NOT EXISTS job_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    job_url TEXT NOT NULL,
    job_title TEXT,
    company_name TEXT,
    platform TEXT, -- greenhouse, lever, ashby, etc.
    
    -- Status tracking
    status TEXT DEFAULT 'discovered', -- discovered, applied, interviewing, offer, rejected
    applied_at TIMESTAMPTZ,
    
    -- Application details
    resume_id UUID REFERENCES generated_resumes(id),
    cover_letter_id UUID REFERENCES cover_letters(id),
    
    -- Job analysis
    match_score INTEGER,
    salary_range TEXT,
    tech_stack TEXT[],
    matching_skills TEXT[],
    missing_skills TEXT[],
    analysis_notes TEXT,
    
    -- Draft mode data
    draft_data JSONB DEFAULT '{}',
    is_draft BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 9. NETWORK CONTACTS (LinkedIn X-Ray results)
-- ============================================================================
CREATE TABLE IF NOT EXISTS network_contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    target_company TEXT NOT NULL,
    name TEXT NOT NULL,
    headline TEXT,
    profile_url TEXT,
    
    connection_type TEXT, -- alumni, location, company, mutual
    college_match TEXT,
    company_match TEXT,
    location_match TEXT,
    
    confidence_score FLOAT DEFAULT 0,
    outreach_draft TEXT,
    outreach_sent BOOLEAN DEFAULT FALSE,
    response_received BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 10. INTERVIEW PREP
-- ============================================================================
CREATE TABLE IF NOT EXISTS interview_prep (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    application_id UUID REFERENCES job_applications(id),
    
    company_name TEXT NOT NULL,
    role TEXT,
    interview_type TEXT, -- technical, behavioral, system_design
    
    questions JSONB DEFAULT '[]',
    answers JSONB DEFAULT '[]',
    feedback JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES for Performance
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_education_user_id ON user_education(user_id);
CREATE INDEX IF NOT EXISTS idx_user_experience_user_id ON user_experience(user_id);
CREATE INDEX IF NOT EXISTS idx_user_projects_user_id ON user_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_user_resumes_user_id ON user_resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_generated_resumes_user_id ON generated_resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_cover_letters_user_id ON cover_letters(user_id);
CREATE INDEX IF NOT EXISTS idx_job_applications_user_id ON job_applications(user_id);
CREATE INDEX IF NOT EXISTS idx_job_applications_status ON job_applications(status);
CREATE INDEX IF NOT EXISTS idx_network_contacts_user_id ON network_contacts(user_id);
CREATE INDEX IF NOT EXISTS idx_interview_prep_user_id ON interview_prep(user_id);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) - Users can only access their own data
-- ============================================================================
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_education ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_experience ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE cover_letters ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_prep ENABLE ROW LEVEL SECURITY;

-- RLS Policies - Users can only see/modify their own rows
CREATE POLICY "Users can view own profile" ON user_profiles FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can update own profile" ON user_profiles FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own profile" ON user_profiles FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can delete own profile" ON user_profiles FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own education" ON user_education FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own education" ON user_education FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own experience" ON user_experience FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own experience" ON user_experience FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own projects" ON user_projects FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own projects" ON user_projects FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own resumes" ON user_resumes FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own resumes" ON user_resumes FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own generated resumes" ON generated_resumes FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own generated resumes" ON generated_resumes FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own cover letters" ON cover_letters FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own cover letters" ON cover_letters FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own applications" ON job_applications FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own applications" ON job_applications FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own network contacts" ON network_contacts FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own network contacts" ON network_contacts FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own interview prep" ON interview_prep FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own interview prep" ON interview_prep FOR ALL USING (auth.uid() = user_id);

-- ============================================================================
-- STORAGE BUCKETS (Run in Supabase Dashboard > Storage)
-- ============================================================================
-- Create these buckets manually in Supabase Dashboard:
-- 1. resumes (private) - For user uploaded resumes
-- 2. generated-resumes (private) - For AI-generated PDFs
-- 3. cover-letters (private) - For generated cover letters

-- Storage policies (run in Dashboard > Storage > Policies):
-- Allow users to upload to their own folder: bucket_id = 'resumes' AND auth.uid()::text = (storage.foldername(name))[1]

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables
CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_education_updated_at BEFORE UPDATE ON user_education FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_experience_updated_at BEFORE UPDATE ON user_experience FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_projects_updated_at BEFORE UPDATE ON user_projects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_resumes_updated_at BEFORE UPDATE ON user_resumes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_job_applications_updated_at BEFORE UPDATE ON job_applications FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
