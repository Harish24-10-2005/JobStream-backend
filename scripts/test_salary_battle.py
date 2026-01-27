
import asyncio
import sys
import os

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.salary_agent import SalaryAgent

async def test_salary_battle():
    print("💰 Testing Salary Negotiation Battle Logic...")
    
    agent = SalaryAgent()
    
    # 1. Battle Context
    context = {
        "role": "Senior Python Developer",
        "initial_offer": 140000,
        "current_offer": 140000,
        "target_salary": 160000,
        "difficulty": "medium",
        "company": "DataCorp"
    }
    
    print(f"\n📋 Context: {context['role']} at {context['company']}")
    print(f"💵 Offer: ${context['initial_offer']:,} -> Target: ${context['target_salary']:,}")
    
    history = []
    
    # turn 1: User asks for more
    user_input = "I'm excited about the role, but given my experience, I was looking for $160k."
    print(f"\n🎤 User: {user_input}")
    
    response = await agent.negotiate_interactive(history, user_input, context)
    
    print(f"🤖 AI Response: {response['response_text']}")
    print(f"📊 Status: {response['status']}")
    print(f"💵 New Offer: {response.get('new_offer')}")
    
    if response and response['status'] in ['active', 'won', 'lost']:
        print("\n✅ Negotiation Logic Test Passed!")
    else:
        print("\n❌ Test Failed: Invalid response structure.")

if __name__ == "__main__":
    asyncio.run(test_salary_battle())
