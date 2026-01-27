"""
Company Service - Manages persistence of company research reports.
"""
from typing import List, Optional, Dict
import logging
from src.services.supabase_client import supabase_client

logger = logging.getLogger(__name__)

class CompanyService:
    """Service for managing company reports in Supabase."""
    
    def __init__(self):
        self.client = supabase_client
        
    async def save_report(self, user_id: str, company_name: str, report_data: Dict) -> Optional[str]:
        """Save a company research report."""
        try:
            data = {
                "user_id": user_id,
                "company_name": company_name,
                "report_data": report_data
            }
            
            response = self.client.table("user_company_reports").insert(data).execute()
            if response.data:
                logger.info(f"Saved report for {company_name}")
                return response.data[0]["id"]
                
        except Exception as e:
            logger.error(f"Failed to save company report: {e}")
            return None

    async def get_report(self, report_id: str, user_id: str) -> Optional[Dict]:
        """Get a specific report."""
        try:
            response = self.client.table("user_company_reports")\
                .select("*")\
                .eq("id", report_id)\
                .eq("user_id", user_id)\
                .single()\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to fetch report {report_id}: {e}")
            return None

    async def get_user_reports(self, user_id: str) -> List[Dict]:
        """List all reports for a user."""
        try:
            response = self.client.table("user_company_reports")\
                .select("id, company_name, created_at")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to fetch reports for user {user_id}: {e}")
            return []

company_service = CompanyService()
