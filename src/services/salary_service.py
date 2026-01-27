
from typing import Dict, List, Optional
import os
import json
from supabase import create_client, Client
from src.core.config import settings
from src.core.console import console

class SalaryService:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not self.url or not self.key:
            console.warning("Supabase credentials missing. SalaryService disabled.")
            self.client = None
        else:
            self.client: Client = create_client(self.url, self.key)

    async def create_battle(self, user_id: str, data: Dict) -> str:
        """Create a new negotiation battle session."""
        if not self.client: return "mock-battle-id"
        
        try:
            payload = {
                "user_id": user_id,
                "role": data.get("role"),
                "company": data.get("company"),
                "location": data.get("location"),
                "initial_offer": data.get("initial_offer"),
                "current_offer": data.get("initial_offer"),
                "target_salary": data.get("target_salary"),
                "difficulty": data.get("difficulty", "medium"),
                "status": "active"
            }
            
            response = self.client.table("user_salary_battles").insert(payload).execute()
            if response.data:
                return response.data[0]["id"]
            return None
        except Exception as e:
            console.error(f"Error creating battle: {e}")
            return None

    async def log_message(self, battle_id: str, role: str, content: str, offer_amount: Optional[int] = None):
        """Log a message in the battle."""
        if not self.client: return
        
        try:
            data = {
                "battle_id": battle_id,
                "role": role,
                "content": content,
                "offer_amount": offer_amount
            }
            self.client.table("user_salary_messages").insert(data).execute()
        except Exception as e:
            console.error(f"Error logging salary message: {e}")

    async def update_battle_status(self, battle_id: str, status: str, current_offer: int = None):
        """Update the battle state (e.g. game over, new offer)."""
        if not self.client: return
        
        try:
            payload = {"status": status}
            if current_offer:
                payload["current_offer"] = current_offer
                
            self.client.table("user_salary_battles").update(payload).eq("id", battle_id).execute()
        except Exception as e:
            console.error(f"Error updating battle: {e}")

    async def get_battle_history(self, battle_id: str) -> List[Dict]:
        """Get chat history for context."""
        if not self.client: return []
        
        try:
            response = self.client.table("user_salary_messages")\
                .select("*")\
                .eq("battle_id", battle_id)\
                .order("created_at")\
                .execute()
            return response.data
        except Exception as e:
            console.error(f"Error fetching history: {e}")
            return []

salary_service = SalaryService()
