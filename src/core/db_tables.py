"""
Centralized Database Table Names
Prevents schema drift by providing a single source of truth for table names.
"""

# Core Tables
PROFILES = "user_profiles"
DOCUMENTS = "documents"  # Primary RAG table
APPLICATIONS = "applications"
RESUMES = "user_resumes"
GENERATED_RESUMES = "user_generated_resumes"
COVER_LETTERS = "user_cover_letters"
JOB_ANALYSES = "job_analyses"

# Salary & Negotiation
SALARY_BATTLES = "user_salary_battles"
SALARY_MESSAGES = "user_salary_messages"

# Service & Auth
CREDENTIALS = "platform_credentials"
SEARCH_METRICS = "job_search_metrics"
SEARCH_RESULTS = "job_search_results"

# Monitoring & Logs
SYSTEM_LOGS = "system_logs"
USER_ACTIVITY = "user_activity"
