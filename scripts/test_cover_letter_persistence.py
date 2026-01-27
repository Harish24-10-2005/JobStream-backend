"""
Test Cover Letter Persistence
"""
import asyncio
import sys
from pathlib import Path

# Add project root
root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, root)

from src.services.resume_storage_service import resume_storage_service

async def test_cover_letter_persistence():
    print("\n🧪 Testing Cover Letter Persistence...")
    
    user_id = "test_user_persistence_001"
    
    # Mock data
    dummy_pdf = b"%PDF-1.4 mock cover letter"
    content = {
        "full_text": "Dear Hiring Manager, I am great for this role...",
        "tone": "enthusiastic"
    }
    
    print("   Saving cover letter...")
    saved = await resume_storage_service.save_cover_letter(
        user_id=user_id,
        pdf_content=dummy_pdf,
        job_url="http://example.com/job",
        job_title="Backend Dev",
        company_name="Startup Inc",
        content=content,
        tone="enthusiastic"
    )
    
    if saved and saved.get("id"):
        print(f"   ✅ Cover letter saved. ID: {saved['id']}")
        
        # Verify Retrieval
        history = await resume_storage_service.get_cover_letters(user_id)
        match = next((c for c in history if c["id"] == saved["id"]), None)
        
        if match:
            print("   ✅ Verified retrieval from history")
            print(f"      PDF URL: {match.get('pdf_url')}")
            print(f"      Tone: {match.get('tone')}")
        else:
            print("   ❌ Failed to find saved cover letter in history")
            
        # Verify Single Get
        single = await resume_storage_service.get_cover_letter(user_id, saved["id"])
        if single:
            print("   ✅ Verified single item retrieval")
        else:
            print("   ❌ Failed single item retrieval")
            
    else:
        print("   ❌ Failed to save cover letter")

if __name__ == "__main__":
    asyncio.run(test_cover_letter_persistence())
