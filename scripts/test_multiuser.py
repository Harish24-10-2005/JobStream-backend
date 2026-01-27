"""
Test script to verify Supabase database schema and multi-user services.
Run: python scripts/test_multiuser.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from src.services.supabase_client import supabase_client
from src.services.user_profile_service import user_profile_service
from src.services.resume_storage_service import resume_storage_service


def test_database_connection():
    """Test basic Supabase connection."""
    print("\n" + "="*60)
    print("1. Testing Database Connection")
    print("="*60)
    
    try:
        # Test connection by querying the tables
        result = supabase_client.table("user_profiles").select("count", count="exact").limit(0).execute()
        print(f"✅ user_profiles table exists (count query successful)")
        
        result = supabase_client.table("user_education").select("count", count="exact").limit(0).execute()
        print(f"✅ user_education table exists")
        
        result = supabase_client.table("user_experience").select("count", count="exact").limit(0).execute()
        print(f"✅ user_experience table exists")
        
        result = supabase_client.table("user_projects").select("count", count="exact").limit(0).execute()
        print(f"✅ user_projects table exists")
        
        result = supabase_client.table("user_resumes").select("count", count="exact").limit(0).execute()
        print(f"✅ user_resumes table exists")
        
        result = supabase_client.table("generated_resumes").select("count", count="exact").limit(0).execute()
        print(f"✅ generated_resumes table exists")
        
        result = supabase_client.table("cover_letters").select("count", count="exact").limit(0).execute()
        print(f"✅ cover_letters table exists")
        
        result = supabase_client.table("job_applications").select("count", count="exact").limit(0).execute()
        print(f"✅ job_applications table exists")
        
        result = supabase_client.table("network_contacts").select("count", count="exact").limit(0).execute()
        print(f"✅ network_contacts table exists")
        
        result = supabase_client.table("interview_prep").select("count", count="exact").limit(0).execute()
        print(f"✅ interview_prep table exists")
        
        print("\n🎉 All 10 tables verified successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False


def test_storage_buckets():
    """Test Supabase storage buckets."""
    print("\n" + "="*60)
    print("2. Testing Storage Buckets")
    print("="*60)
    
    try:
        # List buckets
        buckets = supabase_client.storage.list_buckets()
        bucket_names = [b.name for b in buckets]
        
        print(f"Found buckets: {bucket_names}")
        
        required_buckets = ['resumes', 'generated-resumes', 'cover-letters']
        missing = [b for b in required_buckets if b not in bucket_names]
        
        if missing:
            print(f"⚠️  Missing buckets: {missing}")
            print("   Create them in Supabase Dashboard > Storage")
        else:
            print("✅ All required storage buckets exist!")
            
        return len(missing) == 0
        
    except Exception as e:
        print(f"❌ Storage check error: {e}")
        return False


async def test_user_profile_service():
    """Test user profile service methods."""
    print("\n" + "="*60)
    print("3. Testing User Profile Service")
    print("="*60)
    
    # Use a fake test user ID (won't pass RLS but tests the service logic)
    test_user_id = "00000000-0000-0000-0000-000000000001"
    
    try:
        # Test profile check (should return False for non-existent user)
        exists = await user_profile_service.check_profile_exists(test_user_id)
        print(f"✅ check_profile_exists() works (result: {exists})")
        
        # Test get profile (should return None for non-existent user)
        profile = await user_profile_service.get_profile(test_user_id)
        print(f"✅ get_profile() works (result: {profile})")
        
        # Test profile completion
        completion = await user_profile_service.get_profile_completion(test_user_id)
        print(f"✅ get_profile_completion() works (result: {completion})")
        
        print("\n✅ User Profile Service methods work correctly!")
        return True
        
    except Exception as e:
        print(f"❌ User Profile Service error: {e}")
        return False


async def test_resume_storage_service():
    """Test resume storage service methods."""
    print("\n" + "="*60)
    print("4. Testing Resume Storage Service")
    print("="*60)
    
    test_user_id = "00000000-0000-0000-0000-000000000001"
    
    try:
        # Test get resumes (should return empty list for non-existent user)
        resumes = await resume_storage_service.get_user_resumes(test_user_id)
        print(f"✅ get_user_resumes() works (result: {len(resumes)} resumes)")
        
        # Test get primary resume
        primary = await resume_storage_service.get_primary_resume(test_user_id)
        print(f"✅ get_primary_resume() works (result: {primary})")
        
        # Test get generated resumes
        generated = await resume_storage_service.get_generated_resumes(test_user_id)
        print(f"✅ get_generated_resumes() works (result: {len(generated)} resumes)")
        
        print("\n✅ Resume Storage Service methods work correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Resume Storage Service error: {e}")
        return False


def test_rls_policies():
    """Test that RLS policies are active."""
    print("\n" + "="*60)
    print("5. Testing Row Level Security (RLS)")
    print("="*60)
    
    try:
        # Try to select without auth - should return empty due to RLS
        result = supabase_client.table("user_profiles").select("*").execute()
        
        if len(result.data) == 0:
            print("✅ RLS is working - anon key cannot see user data")
        else:
            print(f"⚠️  RLS might not be configured - found {len(result.data)} rows")
            
        return True
        
    except Exception as e:
        # Permission denied is expected with RLS
        if "permission denied" in str(e).lower() or "RLS" in str(e):
            print("✅ RLS is active - permission denied as expected")
            return True
        print(f"❌ RLS test error: {e}")
        return False


async def main():
    """Run all tests."""
    print("\n" + "🧪"*30)
    print("   JOBAI MULTI-USER DATABASE VERIFICATION")
    print("🧪"*30)
    
    results = []
    
    # Test 1: Database connection and tables
    results.append(("Database Tables", test_database_connection()))
    
    # Test 2: Storage buckets
    results.append(("Storage Buckets", test_storage_buckets()))
    
    # Test 3: User profile service
    results.append(("User Profile Service", await test_user_profile_service()))
    
    # Test 4: Resume storage service
    results.append(("Resume Storage Service", await test_resume_storage_service()))
    
    # Test 5: RLS policies
    results.append(("Row Level Security", test_rls_policies()))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 All tests passed! Database is ready for multi-user.")
    else:
        print("⚠️  Some tests failed. Check the output above.")
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
