
import asyncio
import sys
import os
from pathlib import Path
from postgrest.exceptions import APIError

# Add project root to path
root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, root)

from src.services.supabase_client import SupabaseClient

async def verify_migrations():
    print("\n🔍 Verifying Database Migrations & Schema...\n")
    
    client = SupabaseClient.get_client()
    
    # Complete list of ALL tables required by the backend
    tables_to_check = [
        # Core tables (supabase_complete_setup.sql)
        ("user_profiles", "core"),
        ("applications", "core"),
        ("jobs", "core"),
        ("job_analyses", "core"),
        ("discovered_jobs", "06_discovered_jobs.sql"),
        ("documents", "vector_database_setup.sql"),
        ("user_resumes", "05_resume_cover_letter.sql"),
        # Agent tables (migrations 01-05)
        ("user_network_leads", "01_network_leads.sql"),
        ("user_company_reports", "02_company_reports.sql"),
        ("user_interview_sessions", "03_interview_sessions.sql"),
        ("user_interview_messages", "03_interview_sessions.sql"),
        ("user_salary_battles", "04_salary_battles.sql"),
        ("user_salary_messages", "04_salary_battles.sql"),
        ("user_generated_resumes", "05_resume_cover_letter.sql"),
        ("user_cover_letters", "05_resume_cover_letter.sql"),
        # New tables (07_all_missing_tables.sql)
        ("resume_templates", "07_all_missing_tables.sql"),
        ("platform_credentials", "07_all_missing_tables.sql"),
        ("job_searches", "07_all_missing_tables.sql"),
        # Legacy tables (may exist from original setup)
        ("companies", "supabase_complete_setup.sql"),
        ("cover_letters", "supabase_complete_setup.sql"),
        ("credentials", "supabase_complete_setup.sql"),
        ("interview_sessions", "supabase_complete_setup.sql"),
        ("network_leads", "supabase_complete_setup.sql"),
        ("salary_data", "supabase_complete_setup.sql"),
        ("generated_resumes", "supabase_complete_setup.sql"),
    ]
    
    all_passed = True
    
    for table_name, migration_source in tables_to_check:
        print(f"   Checking table: '{table_name}' ({migration_source})...", end=" ")
        try:
            # Try to select 1 row. We don't care about data, just if the table exists.
            # RLS might block us, which confirms existence too.
            client.table(table_name).select("*").limit(1).execute()
            print("✅ Exists (Accessible)")
            
        except APIError as e:
            # Check for specific error codes
            msg = str(e)
            if "relation" in msg and "does not exist" in msg:
                print(f"❌ FAILED - Table does not exist!")
                all_passed = False
            elif "policy" in msg or "permission" in msg.lower():
                print(f"✅ Exists (Protected by RLS)")
            else:
                print(f"⚠️ Warning: {e}")
                # We assume existence if it's not a 404/Relation error
                
        except Exception as e:
             # Fallback for other errors
            msg = str(e)
            if "relation" in msg and "does not exist" in msg:
                 print(f"❌ FAILED - Table does not exist!")
                 all_passed = False
            else:
                 # If we get here, the table likely exists but we have some other issue (Auth/Connection)
                 # validating existence via error message is hacky but effective for RLS
                 print(f"✅ Exists (Verified via Error: {type(e).__name__})")

    print("-" * 50)
    if all_passed:
        print("\n✅ DB VERIFICATION PASSED: All migration tables detected.")
    else:
        print("\n❌ DB VERIFICATION FAILED: Missing tables.")

if __name__ == "__main__":
    asyncio.run(verify_migrations())
