import sys
import os
import asyncio
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Load env vars
load_dotenv()

from src.services.supabase_client import supabase_client
from src.services.db_service import db_service

async def check_connection():
    print("--- Database Connection Check ---")
    
    # 1. Check client initialization
    if not supabase_client:
        print("❌ Supabase client not initialized")
        return False
        
    print(f"✅ Supabase client initialized")

    # 2. Check table access (discovered_jobs)
    try:
        print("Testing getting discovered jobs...")
        result = db_service.get_discovered_jobs(limit=1)
        
        if "error" in result:
            print(f"❌ Error querying discovered_jobs:")
            print(result['error']) # Print full error
            return False
            
        print(f"✅ Successfully queried discovered_jobs. Total count: {result.get('total')}")
        
    except Exception as e:
        print(f"❌ Exception during query: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    success = asyncio.run(check_connection())
    if success:
        print("\n✅ DB Connection Verified Successfully")
        sys.exit(0)
    else:
        print("\n❌ DB Connection Failed")
        sys.exit(1)
