
import asyncio
import sys
import os

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.interview_agent import InterviewAgent

async def test_persona_chat():
    print("🤖 Testing Interview Agent Persona Logic...")
    
    agent = InterviewAgent()
    
    # 1. Test Settings
    persona = {
        "name": "Barney Stinson (Head of Sales)",
        "role": "Sales Associate",
        "company": "Goliath National Bank",
        "style": "High energy, uses catchphrases, focused on 'awesomeness'."
    }
    
    history = []
    user_input = "Hi, I'm ready for the interview."
    
    print(f"\n🎭 Persona: {persona['name']}")
    print(f"🎤 User: {user_input}")
    
    # 2. Generate Response
    response = await agent.chat_with_persona(history, user_input, persona)
    
    print(f"🤖 AI: {response}")
    
    if response and len(response) > 5:
        print("\n✅ Persona Chat Test Passed!")
    else:
        print("\n❌ Test Failed: No response.")

if __name__ == "__main__":
    asyncio.run(test_persona_chat())
