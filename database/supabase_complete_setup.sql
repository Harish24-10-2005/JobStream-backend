-- ============================================================================
-- JOBSTREAM COMPLETE DATABASE SCHEMA
-- For Fresh Supabase Project Setup
-- ============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 1. USER PROFILES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Basic Information
    first_name TEXT NOT NULL,
    last_name TEXT,
    email TEXT NOT NULL,
    phone TEXT,
    
    -- URLs
    linkedin_url TEXT,
    github_url TEXT,
    portfolio_url TEXT,
    
    -- JSONB Fields for complex data
    personal_info JSONB DEFAULT '{}'::JSONB,
    skills JSONB DEFAULT '{}'::JSONB,
    education JSONB DEFAULT '[]'::JSONB,
    experience JSONB DEFAULT '[]'::JSONB,
    projects JSONB DEFAULT '[]'::JSONB,
    
    -- Metadata
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast user lookup
CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_user_profiles_email ON user_profiles(email);

-- ============================================================================
-- 2. USER RESUMES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- File Information
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    file_type TEXT DEFAULT 'application/pdf',
    
    -- Parsed Data
    parsed_data JSONB DEFAULT '{}'::JSONB,
    
    -- Metadata
    is_primary BOOLEAN DEFAULT FALSE,
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_user_resumes_user_id ON user_resumes(user_id);
CREATE INDEX idx_user_resumes_is_primary ON user_resumes(user_id, is_primary);

-- ============================================================================
-- 3. JOBS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Job Details
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    job_type TEXT, -- 'full-time', 'part-time', 'contract', 'internship'
    work_mode TEXT, -- 'remote', 'hybrid', 'onsite'
    
    -- URLs and IDs
    job_url TEXT,
    job_board TEXT, -- 'linkedin', 'indeed', 'company-website', etc.
    external_id TEXT,
    
    -- Description
    description TEXT,
    requirements TEXT,
    
    -- Salary
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency TEXT DEFAULT 'USD',
    
    -- Application Status
    status TEXT DEFAULT 'saved', -- 'saved', 'applied', 'interviewing', 'offered', 'rejected', 'accepted', 'withdrawn'
    applied_date TIMESTAMP WITH TIME ZONE,
    
    -- Additional Data
    notes TEXT,
    tags TEXT[],
    metadata JSONB DEFAULT '{}'::JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(user_id, status);
CREATE INDEX idx_jobs_company ON jobs(company);
CREATE INDEX idx_jobs_applied_date ON jobs(applied_date);

-- ============================================================================
-- 4. COMPANIES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Company Information
    name TEXT NOT NULL,
    domain TEXT,
    industry TEXT,
    size TEXT, -- 'startup', 'small', 'medium', 'large', 'enterprise'
    location TEXT,
    
    -- URLs
    website TEXT,
    linkedin_url TEXT,
    
    -- Research Data
    description TEXT,
    culture TEXT,
    tech_stack TEXT[],
    benefits TEXT[],
    
    -- AI Generated Reports
    analysis_report JSONB DEFAULT '{}'::JSONB,
    
    -- Metadata
    notes TEXT,
    is_favorite BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_companies_user_id ON companies(user_id);
CREATE INDEX idx_companies_name ON companies(name);
CREATE INDEX idx_companies_domain ON companies(domain);

-- ============================================================================
-- 5. INTERVIEW SESSIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS interview_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    
    -- Interview Details
    interview_type TEXT NOT NULL, -- 'behavioral', 'technical', 'system-design', 'case-study', 'phone-screen'
    company_name TEXT NOT NULL,
    position TEXT NOT NULL,
    
    -- Scheduling
    scheduled_date TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER DEFAULT 60,
    interviewer_name TEXT,
    
    -- Practice Session Data
    questions_asked JSONB DEFAULT '[]'::JSONB,
    answers_given JSONB DEFAULT '[]'::JSONB,
    feedback JSONB DEFAULT '{}'::JSONB,
    
    -- Performance Metrics
    score INTEGER, -- 0-100
    strengths TEXT[],
    weaknesses TEXT[],
    
    -- Status
    status TEXT DEFAULT 'scheduled', -- 'scheduled', 'completed', 'cancelled'
    
    -- Notes
    notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_interview_sessions_user_id ON interview_sessions(user_id);
CREATE INDEX idx_interview_sessions_job_id ON interview_sessions(job_id);
CREATE INDEX idx_interview_sessions_scheduled_date ON interview_sessions(scheduled_date);

-- ============================================================================
-- 6. NETWORK LEADS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS network_leads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id) ON DELETE SET NULL,
    
    -- Contact Information
    name TEXT NOT NULL,
    title TEXT,
    company TEXT,
    email TEXT,
    linkedin_url TEXT,
    phone TEXT,
    
    -- Relationship
    connection_type TEXT, -- 'first-degree', 'second-degree', 'recruiter', 'hiring-manager', 'employee'
    how_met TEXT,
    
    -- Interaction History
    last_contact_date TIMESTAMP WITH TIME ZONE,
    contact_frequency TEXT, -- 'weekly', 'monthly', 'quarterly', 'as-needed'
    interactions JSONB DEFAULT '[]'::JSONB,
    
    -- Status
    status TEXT DEFAULT 'active', -- 'active', 'inactive', 'responded', 'no-response'
    
    -- Notes
    notes TEXT,
    tags TEXT[],
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_network_leads_user_id ON network_leads(user_id);
CREATE INDEX idx_network_leads_company_id ON network_leads(company_id);
CREATE INDEX idx_network_leads_status ON network_leads(user_id, status);

-- ============================================================================
-- 7. SALARY DATA TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS salary_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Position Information
    job_title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    
    -- Salary Details
    base_salary INTEGER NOT NULL,
    bonus INTEGER DEFAULT 0,
    stock_value INTEGER DEFAULT 0,
    total_comp INTEGER GENERATED ALWAYS AS (base_salary + bonus + stock_value) STORED,
    currency TEXT DEFAULT 'USD',
    
    -- Experience
    years_of_experience INTEGER,
    level TEXT, -- 'entry', 'mid', 'senior', 'lead', 'principal', 'staff'
    
    -- Additional Context
    industry TEXT,
    company_size TEXT,
    
    -- Source
    source TEXT, -- 'offer', 'research', 'levels.fyi', 'glassdoor', 'blind'
    is_verified BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_salary_data_user_id ON salary_data(user_id);
CREATE INDEX idx_salary_data_job_title ON salary_data(job_title);
CREATE INDEX idx_salary_data_location ON salary_data(location);

-- ============================================================================
-- 8. COVER LETTERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS cover_letters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    
    -- Content
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    
    -- Generation Details
    company_name TEXT,
    position TEXT,
    key_requirements TEXT[],
    
    -- AI Generation Metadata
    template_used TEXT,
    generation_params JSONB DEFAULT '{}'::JSONB,
    
    -- Status
    is_favorite BOOLEAN DEFAULT FALSE,
    used_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_cover_letters_user_id ON cover_letters(user_id);
CREATE INDEX idx_cover_letters_job_id ON cover_letters(job_id);

-- ============================================================================
-- 9. APPLICATION TRACKING TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    
    -- Application Details
    applied_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    application_method TEXT, -- 'website', 'linkedin', 'email', 'referral'
    
    -- Documents Used
    resume_id UUID REFERENCES user_resumes(id) ON DELETE SET NULL,
    cover_letter_id UUID REFERENCES cover_letters(id) ON DELETE SET NULL,
    
    -- Status Tracking
    status TEXT DEFAULT 'submitted', -- 'submitted', 'viewed', 'screening', 'interviewing', 'offer', 'rejected', 'accepted', 'withdrawn'
    status_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Timeline
    timeline JSONB DEFAULT '[]'::JSONB, -- Array of status changes with timestamps
    
    -- Notes
    notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_applications_user_id ON applications(user_id);
CREATE INDEX idx_applications_job_id ON applications(job_id);
CREATE INDEX idx_applications_status ON applications(user_id, status);

-- ============================================================================
-- 10. CREDENTIALS TABLE (for automation)
-- ============================================================================
CREATE TABLE IF NOT EXISTS credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Platform
    platform TEXT NOT NULL, -- 'linkedin', 'indeed', 'glassdoor', etc.
    
    -- Encrypted Credentials
    encrypted_data TEXT NOT NULL,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_verified TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, platform)
);

CREATE INDEX idx_credentials_user_id ON credentials(user_id);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE salary_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE cover_letters ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE credentials ENABLE ROW LEVEL SECURITY;

-- User Profiles Policies
CREATE POLICY "Users can view own profile" ON user_profiles FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own profile" ON user_profiles FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own profile" ON user_profiles FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own profile" ON user_profiles FOR DELETE USING (auth.uid() = user_id);

-- User Resumes Policies
CREATE POLICY "Users can view own resumes" ON user_resumes FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own resumes" ON user_resumes FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own resumes" ON user_resumes FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own resumes" ON user_resumes FOR DELETE USING (auth.uid() = user_id);

-- Jobs Policies
CREATE POLICY "Users can view own jobs" ON jobs FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own jobs" ON jobs FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own jobs" ON jobs FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own jobs" ON jobs FOR DELETE USING (auth.uid() = user_id);

-- Companies Policies
CREATE POLICY "Users can view own companies" ON companies FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own companies" ON companies FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own companies" ON companies FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own companies" ON companies FOR DELETE USING (auth.uid() = user_id);

-- Interview Sessions Policies
CREATE POLICY "Users can view own interviews" ON interview_sessions FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own interviews" ON interview_sessions FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own interviews" ON interview_sessions FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own interviews" ON interview_sessions FOR DELETE USING (auth.uid() = user_id);

-- Network Leads Policies
CREATE POLICY "Users can view own leads" ON network_leads FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own leads" ON network_leads FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own leads" ON network_leads FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own leads" ON network_leads FOR DELETE USING (auth.uid() = user_id);

-- Salary Data Policies
CREATE POLICY "Users can view own salary data" ON salary_data FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own salary data" ON salary_data FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own salary data" ON salary_data FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own salary data" ON salary_data FOR DELETE USING (auth.uid() = user_id);

-- Cover Letters Policies
CREATE POLICY "Users can view own cover letters" ON cover_letters FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own cover letters" ON cover_letters FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own cover letters" ON cover_letters FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own cover letters" ON cover_letters FOR DELETE USING (auth.uid() = user_id);

-- Applications Policies
CREATE POLICY "Users can view own applications" ON applications FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own applications" ON applications FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own applications" ON applications FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own applications" ON applications FOR DELETE USING (auth.uid() = user_id);

-- Credentials Policies
CREATE POLICY "Users can view own credentials" ON credentials FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own credentials" ON credentials FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own credentials" ON credentials FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own credentials" ON credentials FOR DELETE USING (auth.uid() = user_id);

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at
CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_interview_sessions_updated_at BEFORE UPDATE ON interview_sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_network_leads_updated_at BEFORE UPDATE ON network_leads FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_salary_data_updated_at BEFORE UPDATE ON salary_data FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_cover_letters_updated_at BEFORE UPDATE ON cover_letters FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_applications_updated_at BEFORE UPDATE ON applications FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_credentials_updated_at BEFORE UPDATE ON credentials FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- COMPLETED! 
-- Next Step: Create Storage Bucket for Resumes
-- Run this in Supabase Dashboard > Storage:
-- 1. Create bucket named: "resumes"
-- 2. Make it private
-- 3. Add RLS policy:
--    - Name: "Users can upload own resumes"
--    - Policy: bucket_id = 'resumes' AND auth.uid()::text = (storage.foldername(name))[1]
--    - Allowed operations: INSERT, UPDATE, SELECT, DELETE
-- ============================================================================
