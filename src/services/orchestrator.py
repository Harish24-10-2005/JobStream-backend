"""
Pipeline Orchestrator with Event Streaming
Wraps JobApplicationWorkflow with real-time event emission
Supports multi-user via user_id parameter
"""
import asyncio
import sys
import os
from typing import Optional, Callable, Any
from datetime import datetime

from src.api.websocket import EventEmitter, EventType, manager, AgentEvent


class StreamingPipelineOrchestrator:
    """
    Orchestrates the job application pipeline with real-time event streaming.
    Wraps the existing JobApplicationWorkflow with WebSocket integration.
    Supports multi-user via user_id for per-user profile loading.
    """
    
    def __init__(self, session_id: str = "default", user_id: Optional[str] = None):
        self.session_id = session_id
        self.user_id = user_id  # For multi-user profile loading
        self._manager = manager
        self._is_running = True
    
    async def emit(self, event_type: EventType, agent: str, message: str, data: dict = None):
        """Emit an event to connected clients."""
        event = AgentEvent(
            type=event_type,
            agent=agent,
            message=message,
            data=data or {}
        )
        await self._manager.send_event(self.session_id, event)
    
    def stop(self):
        """Stop the pipeline."""
        self._is_running = False
    
    async def run(
        self, 
        query: str, 
        location: str, 
        min_match_score: int = 70, 
        auto_apply: bool = False,
        use_company_research: bool = False,
        use_resume_tailoring: bool = False,
        use_cover_letter: bool = False
    ):
        """
        Run the full pipeline with event streaming.
        
        Args:
            query: Job search query
            location: Location filter
            min_match_score: Minimum match score
            auto_apply: Auto-apply flag
            use_company_research: Deep company research flag
            use_resume_tailoring: Resume tailoring flag
            use_cover_letter: Cover letter generation flag
        """
        await self.emit(
            EventType.PIPELINE_START,
            "system",
            f"Starting job search for '{query}' in '{location}'",
            {
                "query": query, "location": location, "auto_apply": auto_apply,
                "user_id": self.user_id,
                "options": {
                    "research": use_company_research,
                    "tailor": use_resume_tailoring,
                    "cover_letter": use_cover_letter
                }
            }
        )
        
        try:
            # Import agents
            from src.automators.scout import ScoutAgent
            from src.automators.analyst import AnalystAgent
            from src.agents.company_agent import CompanyAgent
            from src.agents.resume_agent import ResumeAgent
            from src.agents.cover_letter_agent import CoverLetterAgent
            
            from src.models.profile import UserProfile
            from pathlib import Path
            import yaml
            
            # Load profile - from database if user_id provided, fallback to YAML
            await self.emit(EventType.SCOUT_START, "scout", "Loading user profile...")
            
            profile = None
            profile_loaded_from = None
            
            # Try Supabase first if user_id provided
            if self.user_id:
                try:
                    from src.services.user_profile_service import user_profile_service
                    profile = await user_profile_service.get_profile(self.user_id)
                    if profile:
                        profile_loaded_from = "database"
                except Exception as e:
                    print(f"Failed to load profile from database: {e}")
            
            # Fallback to YAML file if no database profile
            if not profile:
                try:
                    # base_dir = src/ (parent of services/)
                    base_dir = Path(__file__).resolve().parent.parent
                    profile_path = base_dir / "data" / "user_profile.yaml"
                    
                    if profile_path.exists():
                        with open(profile_path, "r", encoding="utf-8") as f:
                            profile_data = yaml.safe_load(f)
                        profile = UserProfile(**profile_data)
                        profile_loaded_from = "yaml"
                        await self.emit(EventType.SCOUT_START, "scout", "Using default profile from YAML")
                except Exception as e:
                    print(f"Failed to load profile from YAML: {e}")
            
            if not profile:
                await self.emit(
                    EventType.PIPELINE_ERROR, 
                    "system", 
                    "No user profile found. Please complete onboarding or add user_profile.yaml"
                )
                return {"success": False, "error": "No profile found"}
            
            print(f"Profile loaded from {profile_loaded_from}: {profile.personal_information.full_name}")
            
            # Initialize agents
            scout = ScoutAgent()
            analyst = AnalystAgent()
            
            # Initialize optional agents if needed
            company_agent = CompanyAgent() if use_company_research else None
            resume_agent = ResumeAgent() if use_resume_tailoring else None
            cover_letter_agent = CoverLetterAgent() if use_cover_letter else None

            # HITL Callback Wrapper
            async def hitl_wrapper(question: str, context: str) -> str:
                return await self._manager.request_hitl(self.session_id, question, context)
            
            # ===== SCOUT PHASE =====
            await self.emit(EventType.SCOUT_START, "scout", "Starting job search...")
            await self.emit(EventType.SCOUT_SEARCHING, "scout", f"Searching for '{query}' jobs...")
            
            job_urls = await scout.run(query, location)
            
            await self.emit(
                EventType.SCOUT_FOUND,
                "scout",
                f"Found {len(job_urls)} job listings",
                {"count": len(job_urls), "urls": job_urls[:10]}
            )
            await self.emit(EventType.SCOUT_COMPLETE, "scout", "Job search complete")
            
            if not job_urls:
                await self.emit(EventType.PIPELINE_COMPLETE, "system", "No jobs found", {"applied": 0})
                return {"success": True, "jobs_found": 0}
            
            resume_text = profile.to_resume_text()
            profile_data = profile.model_dump() if hasattr(profile, "model_dump") else dict(profile)
            applied_count = 0
            analyzed_count = 0
            jobs_data = []
            
            # ===== PIPELINE LOOP =====
            for i, url in enumerate(job_urls, 1):
                if not self._is_running:
                    await self.emit(EventType.PIPELINE_COMPLETE, "system", "Stopped by user", {"applied": applied_count})
                    break
                
                await self.emit(
                    EventType.ANALYST_START,
                    "analyst",
                    f"Processing job {i}/{len(job_urls)}",
                    {"job_index": i, "total": len(job_urls), "url": url}
                )
                
                # 1. Analyst
                try:
                    await self.emit(EventType.ANALYST_FETCHING, "analyst", f"Analyzing {url[:40]}...")
                    analysis = await analyst.run(url, resume_text)
                    analyzed_count += 1
                    
                    job_info = {
                        "job_id": f"job_{i}",
                        "url": url,
                        "role": analysis.role,
                        "company": analysis.company,
                        "match_score": analysis.match_score,
                    }
                    
                    await self.emit(
                        EventType.ANALYST_RESULT,
                        "analyst",
                        f"{analysis.company}: {analysis.match_score}% Match",
                        job_info
                    )
                    
                    if analysis.match_score < min_match_score:
                        await self.emit(EventType.ANALYST_RESULT, "analyst", f"Skipping (Score < {min_match_score})")
                        continue

                    # 2. Company Research (Optional)
                    company_research_data = {}
                    if use_company_research and company_agent:
                        await self.emit(EventType.COMPANY_START, "company", f"Researching {analysis.company}...")
                        research_res = await company_agent.run(company=analysis.company, role=analysis.role)
                        
                        if research_res.get("success"):
                            company_research_data = research_res
                            await self.emit(
                                EventType.COMPANY_RESULT, 
                                "company", 
                                f"Research complete for {analysis.company}",
                                research_res # Emit full research results
                            )
                        else:
                            await self.emit(EventType.COMPANY_RESULT, "company", f"Research failed: {research_res.get('error')}")
                    
                    # 3. Resume Tailoring (Optional)
                    tailored_resume_path = None
                    if use_resume_tailoring and resume_agent:
                        await self.emit(EventType.RESUME_START, "resume", f"Tailoring resume for {analysis.role}...")
                        tailoring_res = await resume_agent.run(
                            job_analysis=analysis, 
                            user_profile=profile,
                            hitl_handler=hitl_wrapper
                        )
                        
                        if tailoring_res.get("success") and tailoring_res.get("pdf_path") and tailoring_res.get("human_approved"):
                            tailored_resume_path = tailoring_res.get("pdf_path")
                            await self.emit(
                                EventType.RESUME_COMPLETE,
                                "resume",
                                f"Resume tailored: {os.path.basename(tailored_resume_path)}",
                                {"path": tailored_resume_path}
                            )
                        elif not tailoring_res.get("human_approved"):
                             await self.emit(EventType.RESUME_COMPLETE, "resume", "Tailoring cancelled by user")
                        else:
                            await self.emit(EventType.RESUME_COMPLETE, "resume", "Tailoring failed, using default resume")

                    # 4. Cover Letter Generation (Optional)
                    cover_letter_content = None
                    if use_cover_letter and cover_letter_agent:
                        await self.emit(EventType.COVER_LETTER_START, "cover_letter", f"Drafting cover letter for {analysis.company}...")
                        cl_res = await cover_letter_agent.run(
                            job_analysis=analysis,
                            user_profile=profile,
                            hitl_handler=hitl_wrapper
                        )
                        
                        if cl_res.get("human_approved"):
                            cover_letter_content = cl_res.get("full_text")
                            await self.emit(
                                EventType.COVER_LETTER_COMPLETE,
                                "cover_letter", 
                                "Cover letter generated and approved",
                                {"content": cover_letter_content}
                            )
                        else:
                            await self.emit(EventType.COVER_LETTER_COMPLETE, "cover_letter", "Cover letter generation skipped/cancelled")

                    # 5. Applier (Optional)
                    if auto_apply:
                        await self.emit(EventType.APPLIER_START, "applier", f"Applying to {analysis.company}...")
                        
                        from src.services.ws_applier import WebSocketApplierAgent
                        ws_applier = WebSocketApplierAgent(self.session_id)

                        
                        # Pass tailored resume AND cover letter (if supported by applier later)
                        # For now, just resume_path
                        result = await ws_applier.run(
                            url, 
                            profile_data, 
                            resume_path=tailored_resume_path
                        )
                        
                        if result.get("success"):
                            applied_count += 1
                            await self.emit(
                                EventType.APPLIER_COMPLETE,
                                "applier",
                                "Application successful!",
                                {"job_id": job_info.get("job_id"), "url": url}
                            )
                        else:
                            await self.emit(EventType.PIPELINE_ERROR, "applier", f"Application failed: {result.get('error')}")
                    else:
                        await self.emit(EventType.ANALYST_RESULT, "analyst", "Queued for manual review")
                        
                except Exception as e:
                    await self.emit(EventType.PIPELINE_ERROR, "system", f"Job failed: {e}")
                    continue
                
                await asyncio.sleep(1)

            await self.emit(
                EventType.PIPELINE_COMPLETE,
                "system",
                f"Pipeline finished. Applied to {applied_count} jobs.",
                {"analyzed": analyzed_count, "applied": applied_count}
            )
            
            return {"success": True, "analyzed": analyzed_count, "applied": applied_count}
            
        except Exception as e:
            await self.emit(
                EventType.PIPELINE_ERROR,
                "system",
                f"Pipeline failed: {str(e)}",
                {"error": str(e)}
            )
            return {"success": False, "error": str(e)}
