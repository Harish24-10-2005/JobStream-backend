"""
Job Tracker Agent - Track job applications using Notion
Uses Notion MCP for persistence and tracking
"""
import json
import os
from typing import Dict, List, Optional
from datetime import datetime

from src.automators.base import BaseAgent
from src.core.console import console
from src.core.config import settings


# ============================================
# Notion MCP Integration
# ============================================

class NotionJobTracker:
    """
    Manages job applications in Notion.
    Uses Notion API to create and manage a job tracking database.
    """
    
    def __init__(self, database_id: Optional[str] = None):
        """
        Initialize the Notion job tracker.
        
        Args:
            database_id: Optional existing Notion database ID for job tracking
        """
        self.database_id = database_id
        self._notion_available = self._check_notion_connection()
    
    def _check_notion_connection(self) -> bool:
        """Check if Notion MCP is available."""
        # For now, we'll assume it's available if we get here
        # In production, this would make a test API call
        return True
    
    @property
    def is_connected(self) -> bool:
        return self._notion_available and self.database_id is not None


# ============================================
# Job Application Data Model
# ============================================

class JobApplication:
    """Represents a job application."""
    
    def __init__(
        self,
        company: str,
        role: str,
        status: str = "Applied",
        applied_date: str = None,
        url: str = "",
        salary_range: str = "",
        notes: str = "",
        next_step: str = "",
        last_updated: str = None
    ):
        self.company = company
        self.role = role
        self.status = status
        self.applied_date = applied_date or datetime.now().strftime("%Y-%m-%d")
        self.url = url
        self.salary_range = salary_range
        self.notes = notes
        self.next_step = next_step
        self.priority = priority
        self.last_updated = last_updated or datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "company": self.company,
            "role": self.role,
            "status": self.status,
            "applied_date": self.applied_date,
            "url": self.url,
            "salary_range": self.salary_range,
            "notes": self.notes,
            "next_step": self.next_step,
            "priority": self.priority,
            "last_updated": self.last_updated
        }
    
    def to_notion_properties(self) -> Dict:
        """Convert to Notion database properties format."""
        return {
            "Company": {
                "title": [{"text": {"content": self.company}}]
            },
            "Role": {
                "rich_text": [{"text": {"content": self.role}}]
            },
            "Status": {
                "select": {"name": self.status}
            },
            "Applied Date": {
                "date": {"start": self.applied_date}
            },
            "URL": {
                "url": self.url if self.url else None
            },
            "Salary Range": {
                "rich_text": [{"text": {"content": self.salary_range}}]
            },
            "Notes": {
                "rich_text": [{"text": {"content": self.notes}}]
            },
            "Next Step": {
                "rich_text": [{"text": {"content": self.next_step}}]
            },
            "Priority": {
                "select": {"name": self.priority}
            }
        }


# ============================================
# Tool Functions for Job Tracking
# ============================================

def add_job_application(
    company: str,
    role: str,
    url: str = "",
    salary_range: str = "",
    notes: str = "",
    priority: str = "Medium"
) -> Dict:
    """
    Add a new job application to track.
    
    Args:
        company: Company name
        role: Job title
        url: Job posting URL
        salary_range: Expected salary range
        notes: Any notes about the application
        priority: Priority level (High/Medium/Low)
    
    Returns:
        Confirmation of added application
    """
    console.step(1, 3, f"Adding application: {role} at {company}")
    
    app = JobApplication(
        company=company,
        role=role,
        url=url,
        salary_range=salary_range,
        notes=notes,
        priority=priority
    )
    
    # Store in local tracker (fallback if Notion not connected)
    tracker = JobTrackerAgent._get_local_tracker()
    tracker.append(app.to_dict())
    JobTrackerAgent._save_local_tracker(tracker)
    
    console.success(f"Added: {role} at {company}")
    
    return {
        "success": True,
        "message": f"Added application for {role} at {company}",
        "application": app.to_dict(),
        "total_applications": len(tracker)
    }


def update_application_status(
    company: str,
    role: str = "",
    new_status: str = "In Progress",
    next_step: str = "",
    notes: str = ""
) -> Dict:
    """
    Update the status of an existing job application.
    
    Args:
        company: Company name to search
        role: Optional role to narrow search
        new_status: New status (Applied/In Progress/Interview/Offer/Rejected/Withdrawn)
        next_step: Next action to take
        notes: Additional notes
    
    Returns:
        Updated application info
    """
    console.step(2, 3, f"Updating status for {company}")
    
    tracker = JobTrackerAgent._get_local_tracker()
    
    updated = False
    for app in tracker:
        if app["company"].lower() == company.lower():
            if not role or role.lower() in app["role"].lower():
                app["status"] = new_status
                if next_step:
                    app["next_step"] = next_step
                if notes:
                    app["notes"] = notes
                updated = True
                break
    
    if updated:
        JobTrackerAgent._save_local_tracker(tracker)
        console.success(f"Updated {company} to: {new_status}")
        return {
            "success": True,
            "message": f"Updated {company} status to {new_status}",
            "application": app
        }
    else:
        console.warning(f"Application not found for {company}")
        return {
            "success": False,
            "message": f"No application found for {company}"
        }


def get_applications_by_status(
    status: str = ""
) -> Dict:
    """
    Get all applications, optionally filtered by status.
    
    Args:
        status: Filter by status (Applied/In Progress/Interview/Offer/Rejected)
    
    Returns:
        List of applications matching the filter
    """
    console.step(3, 3, "Fetching applications")
    
    tracker = JobTrackerAgent._get_local_tracker()
    
    if status:
        filtered = [app for app in tracker if app["status"].lower() == status.lower()]
    else:
        filtered = tracker
    
    # Group by status for summary
    by_status = {}
    for app in tracker:
        s = app["status"]
        by_status[s] = by_status.get(s, 0) + 1
    
    console.success(f"Found {len(filtered)} applications")
    
    return {
        "success": True,
        "total": len(tracker),
        "filtered_count": len(filtered),
        "applications": filtered,
        "summary_by_status": by_status
    }


def get_upcoming_actions() -> Dict:
    """
    Get applications with pending next steps/actions.
    
    Returns:
        Applications that need attention
    """
    console.info("Checking for pending actions...")
    
    tracker = JobTrackerAgent._get_local_tracker()
    
    needs_action = []
    interviews = []
    waiting = []
    
    for app in tracker:
        status = app.get("status", "").lower()
        next_step = app.get("next_step", "")
        
        if status == "interview":
            interviews.append(app)
        elif next_step:
            needs_action.append(app)
        elif status in ["applied", "in progress"]:
            waiting.append(app)
    
    return {
        "success": True,
        "interviews_scheduled": interviews,
        "needs_action": needs_action,
        "waiting_for_response": waiting,
        "total_active": len(interviews) + len(needs_action) + len(waiting)
    }


def generate_tracker_report() -> Dict:
    """
    Generate a summary report of all job applications.
    
    Returns:
        Comprehensive tracking report
    """
    console.step(1, 1, "Generating report")
    
    tracker = JobTrackerAgent._get_local_tracker()
    
    # Statistics
    total = len(tracker)
    by_status = {}
    by_priority = {"High": 0, "Medium": 0, "Low": 0}
    
    for app in tracker:
        status = app.get("status", "Unknown")
        by_status[status] = by_status.get(status, 0) + 1
        
        priority = app.get("priority", "Medium")
        if priority in by_priority:
            by_priority[priority] += 1
    
    # Calculate rates
    offers = by_status.get("Offer", 0)
    rejections = by_status.get("Rejected", 0)
    interviews = by_status.get("Interview", 0)
    
    response_rate = ((offers + rejections + interviews) / total * 100) if total > 0 else 0
    interview_rate = ((offers + interviews) / total * 100) if total > 0 else 0
    
    report = {
        "success": True,
        "summary": {
            "total_applications": total,
            "response_rate": f"{response_rate:.1f}%",
            "interview_rate": f"{interview_rate:.1f}%"
        },
        "by_status": by_status,
        "by_priority": by_priority,
        "recent_applications": tracker[-5:] if len(tracker) >= 5 else tracker,
        "recommendations": []
    }
    
    # Add recommendations
    if by_status.get("Applied", 0) > 10 and interviews == 0:
        report["recommendations"].append("Consider updating your resume - many applications but no interviews")
    if offers > 0:
        report["recommendations"].append(f"You have {offers} offer(s)! Time to negotiate salary")
    if total < 5:
        report["recommendations"].append("Apply to more positions to increase your chances")
    
    console.success(f"Report generated: {total} applications tracked")
    return report


# ============================================
# Job Tracker Agent
# ============================================

class JobTrackerAgent(BaseAgent):
    """
    Agent for tracking job applications.
    Integrates with Notion MCP for cloud persistence.
    Falls back to local JSON file if Notion not configured.
    """
    
    
    def __init__(self, user_id: str, notion_database_id: Optional[str] = None):
        super().__init__()
        self.user_id = user_id
        self.notion_tracker = NotionJobTracker(notion_database_id)
        # Use user-specific file in the same directory
        self._local_tracker_file = f"job_applications_{user_id}.json"
    
    def _get_local_tracker(self) -> List[Dict]:
        """Load local tracker from JSON file."""
        import os
        tracker_path = os.path.join(os.path.dirname(__file__), "..", "..", self._local_tracker_file)
        
        if os.path.exists(tracker_path):
            try:
                with open(tracker_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return []
        return []
    
    def _save_local_tracker(self, tracker: List[Dict]):
        """Save local tracker to JSON file."""
        import os
        tracker_path = os.path.join(os.path.dirname(__file__), "..", "..", self._local_tracker_file)
        
        with open(tracker_path, 'w') as f:
            json.dump(tracker, f, indent=2)
    
    async def run(self, *args, **kwargs) -> Dict:
        """Required abstract method."""
        action = kwargs.get('action', 'report')
        
        if action == 'add':
            return self.add_application(
                company=kwargs.get('company', ''),
                role=kwargs.get('role', ''),
                url=kwargs.get('url', ''),
                priority=kwargs.get('priority', 'Medium'),
                salary_range=kwargs.get('salary_range', ''),
                notes=kwargs.get('notes', '')
            )
        elif action == 'update':
            return self.update_application_status(
                company=kwargs.get('company', ''),
                new_status=kwargs.get('status', ''),
                next_step=kwargs.get('next_step', ''),
                notes=kwargs.get('notes', '')
            )
        elif action == 'list':
            return self.get_applications_by_status(kwargs.get('status', ''))
        elif action == 'actions':
            return self.get_upcoming_actions()
        else:
            return self.get_report()
            
    # --- Rewritten Instance Methods replacing the module-level functions ---
    
    async def add_application(
        self,
        company: str,
        role: str,
        url: str = "",
        salary_range: str = "",
        notes: str = "",
        priority: str = "Medium"
    ) -> Dict:
        """Add a new job application."""
        console.subheader("📝 Adding Job Application")
        
        app = JobApplication(
            company=company,
            role=role,
            url=url,
            salary_range=salary_range,
            notes=notes,
            priority=priority
        )
        
        tracker = self._get_local_tracker()
        tracker.append(app.to_dict())
        self._save_local_tracker(tracker)
        
        console.success(f"Added: {role} at {company}")
        return {
            "success": True,
            "message": f"Added application for {role} at {company}",
            "application": app.to_dict(),
            "total_applications": len(tracker)
        }
    
    async def update_status(
        self,
        company: str,
        new_status: str,
        next_step: str = "",
        notes: str = ""
    ) -> Dict:
        """Alias for update_application_status."""
        return await self.update_application_status(company, new_status, next_step, notes)

    async def update_application_status(
        self,
        company: str,
        new_status: str,
        next_step: str = "",
        notes: str = ""
    ) -> Dict:
        """Update application status."""
        console.subheader("🔄 Updating Application")
        
        tracker = self._get_local_tracker()
        updated = False
        app_data = {}
        
        for app in tracker:
            if app["company"].lower() == company.lower():
                app["status"] = new_status
                if next_step:
                    app["next_step"] = next_step
                if notes:
                    app["notes"] = notes
                app["last_updated"] = datetime.now().isoformat()
                updated = True
                app_data = app
                break
        
        if updated:
            self._save_local_tracker(tracker)
            console.success(f"Updated {company} to: {new_status}")
            return {
                "success": True, 
                "message": f"Updated {company} status to {new_status}",
                "application": app_data
            }
        else:
            return {"success": False, "message": f"No application found for {company}"}
    
    async def get_applications_by_status(self, status: str = "") -> Dict:
        """Get applications filtered by status."""
        tracker = self._get_local_tracker()
        if status:
            filtered = [app for app in tracker if app["status"].lower() == status.lower()]
        else:
            filtered = tracker
        return {"success": True, "applications": filtered}

    async def get_upcoming_actions(self) -> Dict:
        """Get pending actions and stale applications."""
        tracker = self._get_local_tracker()
        needs_action = []
        interviews = []
        waiting = []
        stale = []
        
        from datetime import datetime, timedelta
        now = datetime.now()
        
        for app in tracker:
            status = app.get("status", "").lower()
            next_step = app.get("next_step", "")
            
            # Parse last_updated safely
            last_updated_str = app.get("last_updated")
            is_stale = False
            if last_updated_str:
                try:
                    last_updated = datetime.fromisoformat(last_updated_str)
                    if (now - last_updated) > timedelta(days=7) and status == "applied":
                        is_stale = True
                except ValueError:
                    pass

            if status == "interview":
                interviews.append(app)
            elif next_step:
                needs_action.append(app)
            elif is_stale:
                app["suggested_action"] = "Follow up email"
                stale.append(app)
            elif status in ["applied", "in progress"]:
                waiting.append(app)
                
        return {
            "success": True, 
            "total_active": len(tracker),
            "interviews": interviews,
            "needs_action": needs_action,
            "stale_applications": stale,
            "waiting": waiting
        }

    async def get_report(self) -> Dict:
        """Get tracker report."""
        console.subheader("📊 Job Application Report")
        tracker = self._get_local_tracker()
        return {"success": True, "total_applications": len(tracker), "applications": tracker}
    
    async def sync_to_notion(self, parent_page_id: str) -> Dict:
        """Sync local tracker to Notion."""
        tracker = self._get_local_tracker()
        return {"success": True, "message": "Sync not implemented yet", "count": len(tracker)}

# No singleton anymore
# job_tracker_agent = JobTrackerAgent()


# ============================================
# Notion MCP Helper Functions
# ============================================

async def create_notion_job_tracker_database(parent_page_id: str) -> Dict:
    """
    Create a Job Tracker database in Notion.
    
    This function should be called with a valid Notion page ID
    where you want the database created.
    
    Args:
        parent_page_id: The Notion page ID to create the database in
        
    Returns:
        Created database info including ID
    """
    database_properties = {
        "Company": {"title": {}},
        "Role": {"rich_text": {}},
        "Status": {
            "select": {
                "options": [
                    {"name": "Applied", "color": "blue"},
                    {"name": "In Progress", "color": "yellow"},
                    {"name": "Interview", "color": "green"},
                    {"name": "Offer", "color": "purple"},
                    {"name": "Rejected", "color": "red"},
                    {"name": "Withdrawn", "color": "gray"}
                ]
            }
        },
        "Priority": {
            "select": {
                "options": [
                    {"name": "High", "color": "red"},
                    {"name": "Medium", "color": "yellow"},
                    {"name": "Low", "color": "green"}
                ]
            }
        },
        "Applied Date": {"date": {}},
        "Salary Range": {"rich_text": {}},
        "URL": {"url": {}},
        "Next Step": {"rich_text": {}},
        "Notes": {"rich_text": {}}
    }
    
    # This will be called via MCP
    return {
        "properties": database_properties,
        "parent": {"page_id": parent_page_id},
        "title": [{"text": {"content": "JobAI Application Tracker"}}]
    }
