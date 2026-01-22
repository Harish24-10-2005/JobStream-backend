"""
JobAI - Full Workflow Manager
Orchestrates all agents for end-to-end job application pipeline
"""
import asyncio
import yaml
from pathlib import Path
from typing import Optional, List, Dict

from src.core.logger import logger
from src.core.console import console
from src.models.profile import UserProfile
from src.automators.scout import ScoutAgent
from src.automators.analyst import AnalystAgent
from src.automators.applier import ApplierAgent
from src.services.db_service import db_service


class JobApplicationWorkflow:
    """
    Orchestrates the end-to-end job application process.
    Integrates all 9 agents for a complete pipeline.
    """
    
    def __init__(self, use_resume_tailoring: bool = True, use_cover_letter: bool = True):
        """
        Initialize workflow with optional features.
        
        Args:
            use_resume_tailoring: Enable AI resume tailoring
            use_cover_letter: Generate cover letters
        """
        # Core agents (original)
        self.scout = ScoutAgent()
        self.analyst = AnalystAgent()
        self.applier = ApplierAgent()
        
        # Feature flags
        self.use_resume_tailoring = use_resume_tailoring
        self.use_cover_letter = use_cover_letter
        
        # Load user profile
        self.profile = self._load_profile()
        
        # Stats tracking
        self.stats = {
            "total_jobs": 0,
            "analyzed": 0,
            "applied": 0,
            "skipped": 0,
            "resumes_tailored": 0,
            "cover_letters": 0
        }
        
        # Lazy load new agents
        self._resume_agent = None
        self._cover_letter_agent = None
        self._tracker_agent = None
        self._interview_agent = None
        self._company_agent = None
        self._salary_agent = None
    
    # ============================================
    # Lazy Agent Loaders
    # ============================================
    
    @property
    def resume_agent(self):
        if self._resume_agent is None:
            from src.agents.resume_agent import resume_agent
            self._resume_agent = resume_agent
        return self._resume_agent
    
    @property
    def cover_letter_agent(self):
        if self._cover_letter_agent is None:
            from src.agents.cover_letter_agent import cover_letter_agent
            self._cover_letter_agent = cover_letter_agent
        return self._cover_letter_agent
    
    @property
    def tracker_agent(self):
        if self._tracker_agent is None:
            from src.agents.tracker_agent import job_tracker_agent
            self._tracker_agent = job_tracker_agent
        return self._tracker_agent
    
    @property
    def interview_agent(self):
        if self._interview_agent is None:
            from src.agents.interview_agent import interview_agent
            self._interview_agent = interview_agent
        return self._interview_agent
    
    @property
    def company_agent(self):
        if self._company_agent is None:
            from src.agents.company_agent import company_agent
            self._company_agent = company_agent
        return self._company_agent
    
    @property
    def salary_agent(self):
        if self._salary_agent is None:
            from src.agents.salary_agent import salary_agent
            self._salary_agent = salary_agent
        return self._salary_agent
    
    # ============================================
    # Profile Loading
    # ============================================
    
    def _load_profile(self) -> UserProfile:
        try:
            base_dir = Path(__file__).resolve().parent.parent.parent
            profile_path = base_dir / "src/data/user_profile.yaml"
            
            with open(profile_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            return UserProfile(**data)
        except Exception as e:
            logger.critical(f"Failed to load user profile: {e}")
            console.error(f"Failed to load user profile: {e}")
            raise
    
    # ============================================
    # Main Workflow
    # ============================================
    
    async def run(self, query: str, location: str, min_match_score: int = 70):
        """
        Run the full job application pipeline.
        
        Pipeline:
        1. Scout - Find jobs
        2. Analyst - Analyze fit
        3. Resume - Tailor resume (optional)
        4. Cover Letter - Generate (optional)
        5. Applier - Submit application
        6. Tracker - Log application
        """
        console.workflow_start(query, location)
        console.info(f"Resume Tailoring: {'✅' if self.use_resume_tailoring else '❌'}")
        console.info(f"Cover Letters: {'✅' if self.use_cover_letter else '❌'}")
        
        logger.info(f"🚀 Starting Job Application Workflow for '{query}' in '{location}'")
        
        # 1. Scout - Find jobs
        job_urls = await self.scout.run(query, location)
        self.stats["total_jobs"] = len(job_urls)
        
        if not job_urls:
            logger.info("No jobs found. Exiting.")
            console.workflow_no_jobs()
            console.workflow_summary(0, 0, 0, 0)
            return
        
        resume_text = self.profile.to_resume_text()
        
        # 2. Process each job
        for i, url in enumerate(job_urls, 1):
            console.workflow_job_progress(i, len(job_urls), url)
            logger.info(f"--- Processing Job {i}/{len(job_urls)} ---")
            
            # Initialize IDs for database tracking
            job_id = None
            analysis_id = None
            resume_id = None
            cover_letter_id = None
            
            # 3. Analyze fit
            try:
                analysis = await self.analyst.run(url, resume_text)
                self.stats["analyzed"] += 1
                
                # Save discovered job to database
                job_id = db_service.save_discovered_job(
                    url=url,
                    title=analysis.role,
                    company=analysis.company,
                    location=location
                )
                
                # Save analysis to database
                if job_id:
                    analysis_id = db_service.save_job_analysis(
                        job_id=job_id,
                        role=analysis.role,
                        company=analysis.company,
                        match_score=analysis.match_score,
                        tech_stack=getattr(analysis, 'tech_stack', []),
                        matching_skills=analysis.matching_skills,
                        missing_skills=analysis.missing_skills,
                        reasoning=analysis.reasoning or ""
                    )
                    
            except Exception as e:
                logger.error(f"Analysis failed for {url}: {e}")
                console.error(f"Analysis failed: {e}")
                continue
            
            # Check score threshold
            if analysis.match_score < min_match_score:
                console.workflow_skip(
                    reason=f"Score {analysis.match_score} < {min_match_score}",
                    company=analysis.company,
                    role=analysis.role,
                    score=analysis.match_score
                )
                self.stats["skipped"] += 1
                continue
            
            console.workflow_match(analysis.company, analysis.role, analysis.match_score)
            
            # 4. Tailor resume (if enabled)
            tailored_resume = None
            if self.use_resume_tailoring:
                try:
                    console.step(1, 4, "Tailoring resume...")
                    tailored_resume = await self.resume_agent.run(
                        job_analysis=analysis,
                        user_profile=self.profile
                    )
                    self.stats["resumes_tailored"] += 1
                    console.success("Resume tailored")
                    
                    # Save generated resume
                    if tailored_resume:
                        resume_id = db_service.save_generated_resume(
                            tailored_content=tailored_resume,
                            job_title=analysis.role,
                            company=analysis.company,
                            job_url=url
                        )
                        
                except Exception as e:
                    logger.warning(f"Resume tailoring failed: {e}")
                    console.warning(f"Resume tailoring skipped: {e}")
            
            # 5. Generate cover letter (if enabled)
            cover_letter = None
            if self.use_cover_letter:
                try:
                    console.step(2, 4, "Generating cover letter...")
                    cover_letter = await self.cover_letter_agent.run(
                        job_analysis=analysis,
                        user_profile=self.profile
                    )
                    self.stats["cover_letters"] += 1
                    console.success("Cover letter generated")
                    
                    # Save cover letter
                    if cover_letter:
                        cover_letter_id = db_service.save_cover_letter(
                            job_title=analysis.role,
                            company_name=analysis.company,
                            content={"text": str(cover_letter)},
                            job_url=url
                        )
                        
                except Exception as e:
                    logger.warning(f"Cover letter generation failed: {e}")
                    console.warning(f"Cover letter skipped: {e}")
            
            # 6. Apply
            try:
                console.step(3, 4, "Submitting application...")
                await self.applier.run(url, self.profile)
                self.stats["applied"] += 1
                logger.info(f"🎉 Applied to {analysis.company}")
                
                # Save application to database
                if job_id:
                    db_service.save_application(
                        job_id=job_id,
                        analysis_id=analysis_id,
                        resume_id=resume_id,
                        cover_letter_id=cover_letter_id,
                        status="applied"
                    )
                    
            except Exception as e:
                logger.error(f"Application failed for {url}: {e}")
                console.error(f"Application failed: {e}")
                continue
            
            # 7. Track application (local tracker)
            try:
                console.step(4, 4, "Logging to tracker...")
                await self.tracker_agent.add_application(
                    company=analysis.company,
                    role=analysis.role,
                    url=url,
                    priority="High" if analysis.match_score >= 85 else "Medium"
                )
            except Exception as e:
                logger.warning(f"Tracking failed: {e}")
            
            await asyncio.sleep(2)  # Brief pause
        
        # Final summary
        console.divider()
        console.header("📊 WORKFLOW COMPLETE")
        console.workflow_summary(
            total_jobs=self.stats["total_jobs"],
            analyzed=self.stats["analyzed"],
            applied=self.stats["applied"],
            skipped=self.stats["skipped"]
        )
        
        if self.use_resume_tailoring:
            console.info(f"Resumes Tailored: {self.stats['resumes_tailored']}")
        if self.use_cover_letter:
            console.info(f"Cover Letters: {self.stats['cover_letters']}")


# ============================================
# Standalone Agent Runners
# ============================================

class StandaloneAgents:
    """
    Run individual agents without full pipeline.
    Each method is self-contained for CLI usage.
    """
    
    @staticmethod
    async def interview_prep(role: str, company: str, tech_stack: List[str]):
        """Standalone interview preparation."""
        from src.agents.interview_agent import interview_agent
        
        console.header("🎯 Interview Preparation")
        result = await interview_agent.quick_prep(role, company, tech_stack)
        
        if result.get("success"):
            # Display resources
            resources = result.get("resources", {})
            dsa = resources.get("dsa_sheets", [])
            
            console.subheader("📚 DSA Resources")
            for r in dsa[:4]:
                console.info(f"• {r['name']}: {r['url']}")
            
            # Display questions
            behavioral = result.get("behavioral_questions", {})
            questions = behavioral.get("questions", [])
            
            console.subheader("💬 Behavioral Questions")
            for i, q in enumerate(questions[:5], 1):
                print(f"  {i}. {q.get('question', '')[:80]}...")
        
        return result
    
    @staticmethod
    async def salary_research(role: str, location: str, current_offer: int = 0):
        """Standalone salary research."""
        from src.agents.salary_agent import salary_agent
        
        console.header("💰 Salary Research")
        
        if current_offer:
            result = await salary_agent.negotiate_offer(
                role=role,
                location=location,
                current_offer=current_offer
            )
        else:
            result = await salary_agent.research_salary(role, location)
        
        if result.get("success"):
            market = result.get("market_data", {})
            salary_range = market.get("salary_range", {})
            
            console.info(f"Market Range: ${salary_range.get('p25', 0):,} - ${salary_range.get('p90', 0):,}")
            console.info(f"Median: ${salary_range.get('p50', 0):,}")
            
            if current_offer:
                counter = result.get("counter_offer", {})
                console.success(f"Recommended Counter: ${counter.get('recommended_counter', 0):,}")
        
        return result
    
    @staticmethod
    async def company_research(company: str, role: str = ""):
        """Standalone company research."""
        from src.agents.company_agent import company_agent
        
        console.header(f"🏢 Researching {company}")
        result = await company_agent.research_company(company, role)
        
        if result.get("success"):
            info = result.get("company_info", {})
            culture = result.get("culture_analysis", {})
            flags = result.get("red_flags", {})
            insights = result.get("interview_insights", {})
            
            # 1. Overview
            console.subheader("1. Company Overview")
            console.info(f"Industry: {info.get('industry', 'Unknown')}")
            console.info(f"Description: {info.get('mission', 'N/A')}")
            console.info(f"Tech Stack: {', '.join(info.get('tech_stack', []))}")
            if info.get("sources"):
                console.info(f"Sources: {', '.join(info['sources'])}")

            # 2. Culture
            console.subheader("2. Culture & Values")
            console.info(f"Type: {culture.get('culture_type', 'Unknown')}")
            console.info(f"Pros: {', '.join(culture.get('pros', [])[:3])}")
            console.info(f"Cons: {', '.join(culture.get('cons', [])[:3])}")
            if culture.get("sources"):
                console.info(f"Sources: {', '.join(culture['sources'])}")

            # 3. Risk Assessment
            console.subheader("3. Risk Assessment")
            risk = flags.get("overall_risk_level", "Unknown")
            console.info(f"Risk Level: {risk.upper()}")
            for flag in flags.get("company_red_flags", [])[:3]:
                console.warning(f"🚩 {flag.get('flag')} ({flag.get('severity')})")
            if flags.get("sources"):
                 console.info(f"Sources: {', '.join(flags['sources'])}")

            # 4. Interview Intelligence
            console.subheader("4. Interview Intelligence")
            console.info(f"Process: {insights.get('interview_process', {}).get('duration', 'Unknown')}")
            console.info("Tips:")
            for tip in insights.get("tips_from_candidates", [])[:3]:
                console.info(f"• {tip}")
            if insights.get("sources"):
                 console.info(f"Sources: {', '.join(insights['sources'])}")
            
            # Generate and Save Markdown Report
            try:
                report_content = company_agent.generate_report(result)
                filename = f"Company_Research_{company.replace(' ', '_')}.md"
                # Ensure reports directory exists
                reports_dir = Path("reports")
                reports_dir.mkdir(exist_ok=True)
                
                report_path = reports_dir / filename
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(report_content)
                
                console.success(f"📄 Detailed report saved to: {report_path}")
            except Exception as e:
                console.error(f"Failed to save report: {e}")
        
        return result
    
    @staticmethod
    async def resume_tailor(role: str, company: str, job_description: str = ""):
        """Standalone resume tailoring."""
        from src.agents.resume_agent import resume_agent
        from src.models.job import JobAnalysis
        
        # Load profile
        base_dir = Path(__file__).resolve().parent.parent.parent
        profile_path = base_dir / "src/data/user_profile.yaml"
        
        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        profile = UserProfile(**data)
        
        # Create mock job analysis
        job_analysis = JobAnalysis(
            role=role,
            company=company,
            tech_stack=[],
            match_score=80,
            job_description=job_description
        )
        
        console.header("📄 Tailoring Resume")
        result = await resume_agent.run(job_analysis=job_analysis, user_profile=profile)
        
        return result
    
    @staticmethod
    async def tracker_report():
        """Show job tracker report."""
        from src.agents.tracker_agent import job_tracker_agent
        
        console.header("📊 Job Application Report")
        result = await job_tracker_agent.get_report()
        
        if result.get("success"):
            summary = result.get("summary", {})
            console.info(f"Total Applications: {summary.get('total_applications', 0)}")
            console.info(f"Response Rate: {summary.get('response_rate', '0%')}")
            
            by_status = result.get("by_status", {})
            for status, count in by_status.items():
                console.info(f"  {status}: {count}")
        
        return result
    
    @staticmethod
    async def add_application(company: str, role: str, url: str = "", priority: str = "Medium"):
        """Manually add job application."""
        from src.agents.tracker_agent import add_job_application
        
        result = add_job_application(company, role, url, priority=priority)
        
        if result.get("success"):
            console.success(f"Added: {role} at {company}")
        
        return result


if __name__ == "__main__":
    workflow = JobApplicationWorkflow()
    asyncio.run(workflow.run("Software Engineer", "Remote"))
