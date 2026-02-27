"""
Resume Agent - DeepAgent pattern for AI-powered resume tailoring
Uses LangChain's DeepAgent with planning, file system tools, and subagents
https://docs.langchain.com/oss/python/deepagents/
"""
import json
import os
from typing import Dict, Optional, List, Callable, Any
from pydantic import BaseModel, Field

# Note: Using direct function calls instead of DeepAgent pattern
# from langchain_groq import ChatGroq (Removed)

from src.automators.base import BaseAgent
from src.models.profile import UserProfile
from src.models.job import JobAnalysis
from src.services.resume_service import resume_service
from src.services.resume_storage_service import resume_storage_service
from src.services.rag_service import rag_service
from src.core.console import console
from src.core.config import settings
from src.core.structured_logger import slog
from src.core.types import AgentResponse
from src.core.circuit_breaker import CircuitBreaker
from src.core.guardrails import create_input_pipeline
from src.core.llm_provider import get_llm
from src.core.agent_memory import agent_memory

# ============================================
# Pydantic Output Schemas (Anti-Hallucination)
# ============================================
class ExperienceItem(BaseModel):
    company: str
    title: str
    highlights: List[str] = Field(default_factory=list)

class SkillsSection(BaseModel):
    primary: List[str] = Field(default_factory=list)
    secondary: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)

class TailoredResumeModel(BaseModel):
    summary: str
    skills: SkillsSection
    experience: List[ExperienceItem] = Field(default_factory=list)
    tailoring_notes: str

# ============================================
# Circuit Breakers & Guardrails
# ============================================
cb_groq = CircuitBreaker("groq", failure_threshold=5, retry_count=2)
input_guard = create_input_pipeline("medium")

# ============================================
# Tool Definitions for DeepAgent
# ============================================

def extract_job_requirements(
    role: str,
    company: str,
    tech_stack: List[str],
    matching_skills: List[str] = None,
    missing_skills: List[str] = None
) -> Dict:
    """
    Extract and analyze job requirements from job posting data.
    
    Args:
        role: The job title
        company: Company name
        tech_stack: List of technologies required
        matching_skills: Skills that match the candidate's profile
        missing_skills: Skills the candidate is missing
    
    Returns:
        Structured requirements with must-have skills and keywords
    """
    console.step(1, 6, "Extracting job requirements")
    
    requirements = {
        "role": role,
        "company": company,
        "must_have": tech_stack or [],
        "keywords": tech_stack or [],
        "matching_skills": matching_skills or [],
        "missing_skills": missing_skills or [],
        "experience_level": "mid-senior"  # Default
    }
    
    console.success(f"Found {len(requirements['must_have'])} must-have skills")
    return requirements


def tailor_resume_content(
    profile_json: str,
    requirements_json: str,
    feedback: str = "",
    rag_context: str = ""
) -> AgentResponse:
    """
    Tailor resume content based on job requirements.
    This is the main AI tailoring function.
    
    Args:
        profile_json: JSON string of user profile
        requirements_json: JSON string of job requirements
        feedback: Optional feedback for revision
    
    Returns:
        JSON string of tailored resume content
    """
    console.step(3, 6, "Tailoring resume content with AI")
    slog.agent("resume_agent", "tailor_resume_content", has_feedback=bool(feedback), has_rag_context=bool(rag_context))
    
    try:
        profile = json.loads(profile_json)
        requirements = json.loads(requirements_json)
    except json.JSONDecodeError as e:
        return AgentResponse.create_error(f"Invalid JSON: {e}")
    
    feedback_instruction = ""
    if feedback:
        feedback_instruction = f"\n\nADDRESS THIS FEEDBACK:\n{feedback}\n"
    
    # Extract only essential profile fields to minimize tokens
    compact_profile = {
        "name": profile.get("personal_information", {}).get("full_name", ""),
        "skills": profile.get("skills", {}).get("primary", [])[:8],
        "experience": [{"title": exp.get("title", ""), "company": exp.get("company", "")} 
                      for exp in profile.get("experience", [])[:2]]
    }
    
    # Extract learnings if injected from tailor_resume wrapper
    learnings_injection = ""
    if "_agent_learnings" in requirements:
        learnings_injection = requirements.pop("_agent_learnings")
    
    prompt = f"""Tailor resume for {requirements.get('role', '')} at {requirements.get('company', '')}.
Keywords: {', '.join(requirements.get('keywords', [])[:5])}

PROFILE: {json.dumps(compact_profile)}

RELEVANT EXPERIENCE (RAG):
{rag_context}

{learnings_injection}
{feedback_instruction}
Return JSON: {{"summary": "...", "skills": {{"primary": [], "secondary": [], "tools": []}}, "experience": [{{"company": "", "title": "", "highlights": []}}], "tailoring_notes": "..."}}"""
    
    try:
        tailored = get_llm().generate_json(
            prompt=prompt,
            system_prompt="You are an ATS resume expert. Follow all user preferences and learnings strictly.",
            agent_name="resume_agent"
        )
        
        if "error" in tailored:
            raise Exception(tailored["error"])
            
        # 1. Strict Pydantic parsing
        try:
            parsed_resume = TailoredResumeModel.model_validate(tailored)
            tailored = parsed_resume.model_dump()
        except Exception as p_err:
            console.warning(f"Pydantic parsing failed, falling back to raw LLM output: {p_err}")
            
        # 2. Strict Skill Validation against base profile (Anti-Hallucination)
        base_skills = set()
        if isinstance(profile.get("skills"), dict):
            for k, v in profile["skills"].items():
                if isinstance(v, list):
                    base_skills.update([s.lower() for s in v])
        elif isinstance(profile.get("skills"), list):
            base_skills.update([s.lower() for s in profile["skills"]])
            
        if base_skills:
            for skill_cat in ["primary", "secondary", "tools"]:
                if isinstance(tailored.get("skills", {}).get(skill_cat), list):
                    original_skills = tailored["skills"][skill_cat]
                    filtered_skills = []
                    for s in original_skills:
                        # Allow skill if it exists in base skills (case insensitive substring match to allow slight variations)
                        if any(s.lower() in bs or bs in s.lower() for bs in base_skills):
                            filtered_skills.append(s)
                        else:
                            console.warning(f"Removed hallucinated skill: {s}")
                    tailored["skills"][skill_cat] = filtered_skills

        # Preserve original data if not in response
        if "personal_information" not in tailored:
            tailored["personal_information"] = profile.get("personal_information", {})
        if not tailored.get("education"):
            tailored["education"] = profile.get("education", [])
        
        slog.agent("resume_agent", "tailoring_complete", job_title=requirements.get("role", "Unknown"))
        return AgentResponse.create_success(data=tailored)
        
    except Exception as e:
        error_msg = str(e)
        console.error(f"Failed to tailor resume: {e}")
        slog.agent_error("resume_agent", "tailoring_failed", error=str(e))
        return AgentResponse.create_error(str(e))


def generate_latex_resume(
    tailored_content_json: str,
    template_type: str = "ats"
) -> str:
    """
    Generate LaTeX document from tailored content.
    
    Args:
        tailored_content_json: JSON string of tailored resume content
        template_type: Template to use ('ats' or 'modern')
    
    Returns:
        LaTeX source code as string
    """
    console.step(4, 6, "Generating LaTeX document")
    
    try:
        tailored = json.loads(tailored_content_json)
    except json.JSONDecodeError:
        return "% Error: Invalid tailored content JSON"
    
    # This is synchronous for DeepAgent compatibility
    import asyncio
    
    async def get_template():
        return await resume_service.get_template_by_type(template_type)
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, use thread executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, get_template())
                template = future.result()
        else:
            template = asyncio.run(get_template())
    except Exception as e:
        console.warning(f"Could not get template: {e}")
        template = None
    
    if template:
        latex = resume_service.fill_template(
            template["latex_content"],
            tailored,
            tailored
        )
        console.success("LaTeX document generated")
        
        # Save and Compile PDF
        import os
        from datetime import datetime
        
        output_dir = os.path.join(os.getcwd(), "output", "resumes")
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename
        name = tailored.get("personal_information", {}).get("full_name", "Candidate").replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Resume_{name}_{timestamp}"
        
        tex_path = os.path.join(output_dir, f"{filename}.tex")
        pdf_path = os.path.join(output_dir, f"{filename}.pdf")
        
        # Save .tex
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex)
            
        # Compile PDF
        console.info(f"Compiling PDF to {pdf_path}...")
        final_pdf_path = resume_service.compile_to_pdf(latex, pdf_path)
        
        if final_pdf_path:
            console.success(f"PDF generated: {final_pdf_path}")
            return f"Resume compiled successfully to: {final_pdf_path}"
        else:
            console.warning(f"LaTeX PDF compilation failed. LaTeX saved to: {tex_path}")
            console.info("Attempting Markdown-to-PDF fallback...")
            
            fallback_pdf_path = pdf_path.replace(".pdf", "_fallback.pdf")
            fallback_result = resume_service.compile_to_pdf_fallback(tailored, fallback_pdf_path)
            
            if fallback_result:
                console.success(f"Fallback PDF generated: {fallback_result}")
                return f"Resume compiled successfully to: {fallback_result} (Using Fallback template)"
            else:
                return f"LaTeX saved to {tex_path} (All PDF compilations failed)"
            
    else:
        console.warning("No template found")
        return "% No template available"


def calculate_ats_score(
    tailored_content_json: str,
    tech_stack: List[str]
) -> int:
    """
    Calculate ATS compatibility score for the tailored resume.
    
    Args:
        tailored_content_json: JSON string of tailored resume content
        tech_stack: Required technologies from job posting
    
    Returns:
        Score from 0-100
    """
    console.step(5, 6, "Calculating ATS compatibility score")
    
    try:
        tailored = json.loads(tailored_content_json)
    except json.JSONDecodeError:
        return 50  # Default score on error
    
    score = resume_service.calculate_ats_score(
        tailored,
        {"tech_stack": tech_stack}
    )
    
    console.score_display(score, "ATS Score")
    return score


async def request_human_approval(
    summary: str,
    tailoring_notes: str,
    ats_score: int,
    role: str,
    company: str,
    resume_path: str = "Not specified",
    hitl_handler: Optional[Callable[[str, str], Any]] = None
) -> Dict:
    """
    Request human approval for the tailored resume.
    This is the Human-in-the-Loop step.
    
    Args:
        summary: The tailored professional summary
        tailoring_notes: Notes about changes made
        ats_score: The calculated ATS score
        role: Target job role
        company: Target company
        resume_path: Path to the generated resume file
        hitl_handler: Async callback for WebSocket HITL (question, context) -> response_str
    
    Returns:
        Dict with 'approved' (bool), 'feedback' (str)
    """
    console.step(6, 6, "Human Review Required")
    console.divider()
    console.header("📋 RESUME REVIEW")
    
    context = f"""
Target Job:
Role: {role}
Company: {company}
ATS Score: {ats_score}/100
Resume: {resume_path}

Tailored Summary:
{summary}

Changes Made:
{tailoring_notes}
    """
    
    console.box("Review Context", context)
    
    # Try to open the PDF if it exists and we are local
    import os
    if resume_path and resume_path.endswith(".pdf") and os.path.exists(resume_path):
        try:
            # Only open locally if no handler (CLI mode) or if explicitly desired
            # logic could be refined but this is fine for now
            if not hitl_handler: 
                os.startfile(resume_path)
                console.info(f"Opened resume for review: {resume_path}")
        except Exception:
            pass
    
    console.divider()
    
    question = "Do you approve this tailored resume? (y/n/e)"
    
    if hitl_handler:
        console.info("Waiting for remote human approval via WebSocket...")
        response = await hitl_handler(question, context)
        # Simplify response parsing for WS
        choice = response.strip().lower()
        # Handle simple 'y' or 'approve'
        if choice in ['y', 'yes', 'approve']:
            console.success("Resume approved via WebSocket!")
            return {"approved": True, "feedback": ""}
        elif choice.startswith('e') or choice.startswith('edit'):
            # Ideally WS client sends "edit: feedback..."
            parts = choice.split(':', 1)
            feedback = parts[1].strip() if len(parts) > 1 else "Please revise based on context."
            console.info(f"Feedback received: {feedback}")
            return {"approved": False, "feedback": feedback}
        else:
            return {"approved": False, "feedback": "Please revise the resume."}

    # CLI Fallback
    console.applier_human_input(question)
    print("\n  Options:")
    print("    [y] Approve and continue")
    print("    [n] Reject and revise")
    print("    [e] Edit with feedback")
    print("    [q] Quit/Cancel")
    
    # Use asyncio.to_thread to make input non-blocking if needed, 
    # but for simple CLI script usage input() is fine.
    # If running in async loop without handler, input() pauses loop which is okay for local dev.
    choice = input("\n  Your choice > ").strip().lower()
    
    if choice == 'y':
        console.success("Resume approved!")
        return {"approved": True, "feedback": ""}
    elif choice == 'e':
        feedback = input("  Enter your feedback > ").strip()
        console.info(f"Feedback received: {feedback}")
        return {"approved": False, "feedback": feedback}
    elif choice == 'n':
        return {"approved": False, "feedback": "Please revise the resume"}
    else:
        console.warning("Resume generation cancelled")
        return {"approved": False, "feedback": "", "cancelled": True}


# ============================================
# Resume DeepAgent System Prompt
# ============================================

RESUME_AGENT_SYSTEM_PROMPT = """You are an expert resume tailoring agent. Your job is to create ATS-optimized, 
tailored resumes that maximize job application success rates.

## Your Capabilities

You have access to the following tools:

### `extract_job_requirements`
Use this to analyze job requirements from the provided job data. Call this first to understand what the job needs.

### `tailor_resume_content`
Use this to tailor the candidate's resume content for the specific job. Pass the user profile and requirements as JSON strings.
If the human provides feedback, include it in the `feedback` parameter for revision.

### `generate_latex_resume`
Use this to generate a professional LaTeX document from the tailored content.
RETURNS: A string containing the path to the compiled PDF (or error).

### `calculate_ats_score`
Use this to calculate how well the tailored resume matches ATS requirements.

### `request_human_approval`
ALWAYS use this before finalizing. The human must approve the tailored resume.
ARGUMENT `resume_path`: You MUST pass the PDF path returned by `generate_latex_resume` here so the human can see it.

## Workflow

1. **Plan** - Use write_todos to break down the task
2. **Extract Requirements** - Analyze the job posting
3. **Tailor Content** - Rewrite the resume for the job
4. **Generate LaTeX & PDF** - Create professional document and **SAVE THE PATH**
5. **Calculate Score** - Check ATS compatibility
6. **Get Approval** - Call `request_human_approval` with `resume_path`
7. **Revise if needed** - If human provides feedback, tailor again

## Important Rules

- ALWAYS get human approval before completing
- If human gives feedback, revise the resume and ask again
- Focus on ATS optimization and keyword matching
- Highlight relevant experience and skills
- Use action verbs and quantifiable achievements
"""


class ResumeAgent(BaseAgent):
    """
    Simple Resume Tailoring Agent.
    
    Uses direct function calls instead of DeepAgent for:
    - Better rate limit handling
    - Simpler debugging
    - Faster execution
    """
    
    def __init__(self):
        super().__init__()
        
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is not set. Please configure it in .env")
    
    async def run(self, *args, **kwargs) -> Dict:
        """Required abstract method - delegates to tailor_resume."""
        job_analysis = kwargs.get('job_analysis') or (args[0] if args else None)
        user_profile = kwargs.get('user_profile') or (args[1] if len(args) > 1 else None)
        template_type = kwargs.get('template_type', 'ats')
        hitl_handler = kwargs.get('hitl_handler', None)
        
        if not job_analysis or not user_profile:
            return AgentResponse.create_error("job_analysis and user_profile are required")
        
        user_id = kwargs.get('user_id', None)
        return await self.tailor_resume(job_analysis, user_profile, template_type, hitl_handler, user_id)
    
    async def tailor_resume(
        self,
        job_analysis: JobAnalysis,
        user_profile: UserProfile,
        template_type: str = "ats",
        hitl_handler: Optional[Callable[[str, str], Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        Tailor a resume using direct function calls.
        
        Args:
            job_analysis: Analysis of the target job
            user_profile: User's base profile
            template_type: Resume template ('ats', 'modern')
            hitl_handler: Optional callback for HITL
            
        Returns:
            Dict with tailored resume content and metadata
        """
        console.subheader("📝 Resume Agent")
        console.info("Starting resume tailoring...")
        
        # Convert to dicts
        job_data = job_analysis.model_dump() if hasattr(job_analysis, 'model_dump') else dict(job_analysis)
        profile_data = user_profile.model_dump() if hasattr(user_profile, 'model_dump') else dict(user_profile)
        
        # Sanitize critical string fields
        for data_dict, dict_name in [(job_data, "job_data"), (profile_data, "profile_data")]:
            for key, val in list(data_dict.items()):
                if isinstance(val, str) and val:
                    check = input_guard.check_sync(val)
                    if check.is_blocked:
                        slog.agent_error("resume_agent", f"guardrail_blocked_{dict_name}_{key}", {"reason": check.blocked_reason})
                        return AgentResponse.create_error(f"Input validation failed for {dict_name}.{key}: {check.blocked_reason}")
                    data_dict[key] = check.processed_text
                elif isinstance(val, list):
                    sanitized_list = []
                    for item in val:
                        if isinstance(item, str):
                            check = input_guard.check_sync(item)
                            if check.is_blocked:
                                slog.agent_error("resume_agent", f"guardrail_blocked_{dict_name}_{key}_item", {"reason": check.blocked_reason})
                                return AgentResponse.create_error(f"Input validation failed for {dict_name}.{key} item: {check.blocked_reason}")
                            sanitized_list.append(check.processed_text)
                        else:
                            sanitized_list.append(item)
                    data_dict[key] = sanitized_list

        try:
            # Step 1: Extract job requirements
            requirements = extract_job_requirements(
                role=job_data.get('role', ''),
                company=job_data.get('company', ''),
                tech_stack=job_data.get('tech_stack', []),
                matching_skills=job_data.get('matching_skills', []),
                missing_skills=job_data.get('missing_skills', [])
            )
            requirements_json = json.dumps(requirements)
            
            # Step 1.5: RAG Context Retrieval
            console.step(2, 6, "Retrieving relevant context from RAG")
            rag_context = ""
            if user_profile.id:
                try:
                    query = f"Experience with {', '.join(requirements['must_have'][:3])} for {requirements['role']}"
                    rag_results = await rag_service.query(user_profile.id, query, limit=3)
                    rag_context = "\n".join([r['content'] for r in rag_results])
                    console.info(f"Found {len(rag_results)} relevant RAG snippets")
                except Exception as rag_err:
                    console.warning(f"RAG lookup failed (proceeding without): {rag_err}")

            # Step 1.8: Fetch Agent Learnings
            console.step(3, 7, "Fetching personal agent learnings")
            learnings_prompt = ""
            if user_id:
                learnings = await agent_memory.get_learnings("resume_agent", user_id)
                if learnings:
                    bullets = "\n".join(f"- {l}" for l in learnings)
                    learnings_prompt = f"\n\n## Personal Learnings & Preferences\nKeep these in mind while generating:\n{bullets}\n"
                    console.info(f"Injected {len(learnings)} personal learnings into context")

            # Step 2: Tailor resume content
            console.step(4, 7, "Tailoring resume content with AI")
            
            # Injecting learnings into tailored prompt
            full_req_json = requirements_json
            if learnings_prompt:
                # Append to requirements so tailor_resume_content gets it
                req_dict = json.loads(requirements_json)
                req_dict["_agent_learnings"] = learnings_prompt
                full_req_json = json.dumps(req_dict)
                
            tailored_json = tailor_resume_content(
                profile_json=json.dumps(profile_data),
                requirements_json=full_req_json,
                rag_context=rag_context
            )
            tailored_content = json.loads(tailored_json)
            
            # Step 3: Generate LaTeX and PDF
            console.step(4, 6, "Generating LaTeX document")
            latex_result = generate_latex_resume(
                tailored_content_json=tailored_json,
                template_type=template_type
            )
            
            # Step 4: Calculate ATS score
            ats_score = calculate_ats_score(
                tailored_content_json=tailored_json,
                tech_stack=job_data.get('tech_stack', [])
            )
            
            # Step 5: Request human approval
            console.step(6, 6, "Requesting human approval")
            approval_result = await request_human_approval(
                role=job_data.get('role', 'Unknown Role'),
                company=job_data.get('company', 'Unknown Company'),
                summary=tailored_content.get('summary', 'No summary generated'),
                tailoring_notes=tailored_content.get('tailoring_notes', 'No notes'),
                ats_score=ats_score,
                resume_path=latex_result if latex_result.endswith('.pdf') else None,
                hitl_handler=hitl_handler
            )
            
            # Step 7: Persistence
            if approval_result.get("approved"):
                console.info("Saving generated resume...")
                try:
                    pdf_bytes = None
                    if latex_result.endswith('.pdf'):
                        with open(latex_result, 'rb') as f:
                            pdf_bytes = f.read()
                    
                    if pdf_bytes and user_profile.id:
                        await resume_storage_service.save_generated_resume(
                            user_id=user_profile.id,
                            pdf_content=pdf_bytes,
                            job_url=job_data.get('job_url'),
                            job_title=job_data.get('role'),
                            company_name=job_data.get('company'),
                            tailored_content=tailored_content,
                            latex_source=latex_result if not latex_result.endswith('.pdf') else None,
                            ats_score=ats_score
                        )
                        console.success("Resume saved to history")
                except Exception as save_err:
                    console.error(f"Failed to save resume: {save_err}")

            return {
                "success": True,
                "tailored_content": tailored_content,
                "latex_source": latex_result if not latex_result.endswith('.pdf') else None,
                "pdf_path": latex_result if latex_result.endswith('.pdf') else None,
                "ats_score": ats_score,
                "human_approved": approval_result.get("approved", False),
                "job_title": job_data.get('role', ''),
                "company_name": job_data.get('company', '')
            }
            
        except Exception as e:
            slog.agent_error("resume_agent", "tailor_resume", str(e))
            return {"error": str(e)}
    
    async def generate_pdf(
        self,
        latex_source: str,
        output_path: str = None
    ) -> Optional[str]:
        """Generate PDF from LaTeX source."""
        if not latex_source or latex_source.startswith("% Error") or latex_source.startswith("% No"):
            console.error("No valid LaTeX source available")
            return None
        
        console.info("Compiling PDF...")
        result = resume_service.compile_to_pdf(latex_source, output_path)
        
        if result:
            console.success(f"PDF generated: {output_path or 'in memory'}")
        else:
            console.error("PDF compilation failed. Install pdflatex.")
        
        return result


# Lazy singleton instance
_resume_agent = None

def get_resume_agent() -> ResumeAgent:
    """Get or create the ResumeAgent singleton."""
    global _resume_agent
    if _resume_agent is None:
        _resume_agent = ResumeAgent()
    return _resume_agent

# For backwards compatibility
resume_agent = None  # Use get_resume_agent() instead
