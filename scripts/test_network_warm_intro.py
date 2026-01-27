
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.profile import UserProfile, PersonalInfo, Location, Urls, NetworkMatch, Files
from src.agents.network_agent import NetworkAgent

# Mock Data
mock_profile = UserProfile(
    personal_information=PersonalInfo(
        first_name="Test", last_name="User", full_name="Test User",
        email="test@example.com", phone="123",
        location=Location(city="San Francisco", country="US", address="SF"),
        urls=Urls()
    ),
    education=[], experience=[], projects=[], 
    files=Files(resume="dummy_path.pdf"),
    skills={"primary": ["Python", "FastAPI", "React", "AWS"]},
    application_preferences=None
)

mock_match = NetworkMatch(
    name="Jane Doe",
    headline="Senior Python Engineer at Google | AWS Expert",
    profile_url="http://linkedin.com/in/jane",
    connection_type="location",
    location_match="San Francisco"
)

async def test_warm_intro():
    print("🧪 Testing Warm Intro Generation...")
    
    agent = NetworkAgent()
    
    # Mock LLM to avoid Groq calls and return a predictable response
    mock_llm = MagicMock()
    mock_llm.ainvoke.return_value.content = "Hi Jane, saw we're neighbors in SF and share a Python/AWS stack. Would love to connect!"
    agent._llm = mock_llm
    
    # Mock settings to avoid validation errors
    agent.settings = MagicMock()
    agent.settings.groq_api_key.get_secret_value.return_value = "fake_key"
    
    # Run generation
    msg = await agent._generate_outreach(mock_match, mock_profile, "Google")
    
    print(f"\n✅ Generated Message:\n{msg}\n")
    
    # Verify the prompt contained our "Common Ground" logic
    call_args = mock_llm.ainvoke.call_args[0][0] # First arg, first item (list)
    prompt_text = call_args[0].content
    
    print("🔍 Verification of Prompt Logic:")
    if "San Francisco" in prompt_text:
        print("   - [PASS] Detected Location Match")
    else:
        print("   - [FAIL] Missed Location Match")
        
    if "Python" in prompt_text or "AWS" in prompt_text:
        print("   - [PASS] Detected Shared Tech Stack (Python/AWS)")
    else:
        print("   - [FAIL] Missed Shared Tech Stack")

if __name__ == "__main__":
    asyncio.run(test_warm_intro())
