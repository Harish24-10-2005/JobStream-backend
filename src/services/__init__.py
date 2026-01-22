"""
Core Services Module - Database, credentials, resume management
Lazy imports to avoid circular dependencies
"""

def get_supabase_client():
    from src.services.supabase_client import supabase_client
    return supabase_client

def get_credential_service():
    from src.services.credential_service import CredentialService
    return CredentialService()

def get_resume_service():
    from src.services.resume_service import ResumeService
    return ResumeService()

def get_db_service():
    from src.services.db_service import db_service
    return db_service

__all__ = [
    "get_supabase_client",
    "get_credential_service",
    "get_resume_service",
    "get_db_service",
]
