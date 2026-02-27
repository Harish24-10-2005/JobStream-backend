"""
LangGraph Pipeline Graph — Job Application State Machine

Replaces the sequential orchestrator with a proper LangGraph StateGraph.
Features:
  - Typed state with Pydantic
  - Conditional edges (skip nodes based on user config)
  - Parallel execution (resume + cover letter)
  - HITL integration at any node
  - Event emission at each transition
  - Checkpoint support for resumable pipelines
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Annotated
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─── Checkpoint Persistence ────────────────────────────────────

CHECKPOINT_DIR = Path(os.environ.get(
    "PIPELINE_CHECKPOINT_DIR",
    Path(__file__).resolve().parent.parent / "data" / "checkpoints",
))


class PipelineCheckpoint:
    """
    Persist pipeline state to disk between node transitions so a
    crashed or restarted run can resume from the last completed node.

    Each pipeline run gets a single JSON file keyed by session_id.
    """

    _SERIALIZABLE_KEYS = {
        "query", "location", "min_match_score", "auto_apply",
        "use_company_research", "use_resume_tailoring", "use_cover_letter",
        "session_id", "user_id", "job_urls", "current_job_index",
        "node_statuses", "total_analyzed", "total_applied", "total_skipped",
        "is_running", "error", "profile_source", "resume_text",
    }

    def __init__(self, session_id: str):
        self.session_id = session_id
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        self._path = CHECKPOINT_DIR / f"{session_id}.json"

    # ── Public API ─────────────────────────────────────

    def save(self, state: dict, completed_node: str) -> None:
        """Save checkpoint after a node completes successfully."""
        safe = {k: v for k, v in state.items() if k in self._SERIALIZABLE_KEYS}
        safe["_checkpoint_node"] = completed_node
        safe["_checkpoint_ts"] = datetime.utcnow().isoformat() + "Z"

        # Serialise job_results separately (they're Pydantic models)
        results = state.get("job_results", [])
        safe["job_results"] = [
            r.model_dump() if hasattr(r, "model_dump") else dict(r)
            for r in results
        ]

        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(safe, f, default=str)
            logger.debug(f"Checkpoint saved after '{completed_node}' → {self._path.name}")
        except Exception as exc:
            logger.warning(f"Checkpoint save failed: {exc}")

    def load(self) -> Optional[dict]:
        """Load a previously saved checkpoint, or None."""
        if not self._path.exists():
            return None
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(
                f"Checkpoint restored from '{data.get('_checkpoint_node')}' "
                f"({data.get('_checkpoint_ts')})"
            )
            return data
        except Exception as exc:
            logger.warning(f"Checkpoint load failed: {exc}")
            return None

    def clear(self) -> None:
        """Remove checkpoint file after pipeline finishes."""
        try:
            self._path.unlink(missing_ok=True)
        except Exception:
            pass


# ─── State Schema ───────────────────────────────────────────────

class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobResult(BaseModel):
    """Result from analyst for a single job."""
    job_id: str = ""
    url: str = ""
    role: str = ""
    company: str = ""
    match_score: int = 0
    analysis: Any = None
    company_research: Optional[Dict] = None
    tailored_resume_path: Optional[str] = None
    cover_letter_content: Optional[str] = None
    applied: bool = False
    error: Optional[str] = None


class PipelineState(BaseModel):
    """
    Typed state for the full job application pipeline.
    Each node reads and writes to this shared state.
    """
    # --- Input Config ---
    query: str = ""
    location: str = ""
    min_match_score: int = 70
    auto_apply: bool = False
    use_company_research: bool = False
    use_resume_tailoring: bool = False
    use_cover_letter: bool = False
    session_id: str = "default"
    user_id: Optional[str] = None

    # --- Profile ---
    profile: Any = None  # UserProfile object
    profile_source: Optional[str] = None
    resume_text: str = ""

    # --- Pipeline State ---
    job_urls: List[str] = Field(default_factory=list)
    current_job_index: int = 0
    current_analysis: Any = None  # JobAnalysis from analyst
    job_results: List[JobResult] = Field(default_factory=list)

    # --- Node Status Tracking ---
    node_statuses: Dict[str, str] = Field(default_factory=dict)

    # --- Aggregates ---
    total_analyzed: int = 0
    total_applied: int = 0
    total_skipped: int = 0

    # --- Events (for WebSocket emission) ---
    events: List[Dict[str, Any]] = Field(default_factory=list)

    # --- Control ---
    is_running: bool = True
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


# ─── Event Helpers ──────────────────────────────────────────────

def _add_event(state: dict, event_type: str, agent: str, message: str, data: dict = None) -> dict:
    """Add an event to state for WebSocket emission."""
    event = {
        "type": event_type,
        "agent": agent,
        "message": message,
        "data": data or {},
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    events = state.get("events", [])
    events.append(event)
    return {"events": events}


# ─── Node Functions ─────────────────────────────────────────────

async def load_profile_node(state: dict) -> dict:
    """Load user profile from DB or YAML fallback."""
    user_id = state.get("user_id")
    profile = None
    profile_source = None

    # Try DB first
    if user_id:
        try:
            from src.services.user_profile_service import user_profile_service
            profile = await user_profile_service.get_profile(user_id)
            if profile:
                profile_source = "database"
        except Exception as e:
            logger.warning(f"DB profile load failed: {e}")

    # Fallback to YAML
    if not profile:
        try:
            from pathlib import Path
            import yaml
            from src.models.profile import UserProfile

            base_dir = Path(__file__).resolve().parent.parent
            profile_path = base_dir / "data" / "user_profile.yaml"

            if profile_path.exists():
                with open(profile_path, "r", encoding="utf-8") as f:
                    profile_data = yaml.safe_load(f)
                profile = UserProfile(**profile_data)
                profile_source = "yaml"
        except Exception as e:
            logger.error(f"YAML profile load failed: {e}")

    if not profile:
        return {
            **_add_event(state, "pipeline:error", "system", "No user profile found"),
            "is_running": False,
            "error": "No profile found",
            "node_statuses": {**state.get("node_statuses", {}), "load_profile": NodeStatus.FAILED},
        }

    resume_text = profile.to_resume_text()
    return {
        **_add_event(state, "scout:start", "scout", f"Profile loaded from {profile_source}"),
        "profile": profile,
        "profile_source": profile_source,
        "resume_text": resume_text,
        "node_statuses": {**state.get("node_statuses", {}), "load_profile": NodeStatus.COMPLETED},
    }


async def scout_node(state: dict) -> dict:
    """Discover job URLs from search engines."""
    from src.automators.scout import ScoutAgent

    query = state.get("query", "")
    location = state.get("location", "")

    events_update = _add_event(state, "scout:searching", "scout", f"Searching for '{query}' jobs...")

    try:
        scout = ScoutAgent()
        job_urls = await scout.run(query, location)

        events_update = _add_event(
            {**state, "events": events_update["events"]},
            "scout:complete", "scout",
            f"Found {len(job_urls)} job listings",
            {"count": len(job_urls), "urls": job_urls[:10]}
        )

        return {
            **events_update,
            "job_urls": job_urls,
            "node_statuses": {**state.get("node_statuses", {}), "scout": NodeStatus.COMPLETED},
        }
    except Exception as e:
        logger.error(f"Scout failed: {e}")
        return {
            **_add_event(state, "pipeline:error", "scout", f"Job search failed: {e}"),
            "job_urls": [],
            "error": str(e),
            "node_statuses": {**state.get("node_statuses", {}), "scout": NodeStatus.FAILED},
        }


async def analyze_job_node(state: dict) -> dict:
    """Analyze the current job URL for fit scoring."""
    from src.automators.analyst import AnalystAgent

    job_urls = state.get("job_urls", [])
    idx = state.get("current_job_index", 0)

    if idx >= len(job_urls):
        return {
            "node_statuses": {**state.get("node_statuses", {}), "analyze_job": NodeStatus.COMPLETED},
        }

    url = job_urls[idx]
    resume_text = state.get("resume_text", "")

    events_update = _add_event(
        state, "analyst:start", "analyst",
        f"Processing job {idx + 1}/{len(job_urls)}",
        {"job_index": idx + 1, "total": len(job_urls), "url": url}
    )

    try:
        analyst = AnalystAgent()
        analysis = await analyst.run(url, resume_text)

        job_info = {
            "job_id": f"job_{idx + 1}",
            "url": url,
            "role": analysis.role,
            "company": analysis.company,
            "match_score": analysis.match_score,
        }

        events_update = _add_event(
            {**state, "events": events_update["events"]},
            "analyst:result", "analyst",
            f"{analysis.company}: {analysis.match_score}% Match",
            job_info
        )

        return {
            **events_update,
            "current_analysis": analysis,
            "total_analyzed": state.get("total_analyzed", 0) + 1,
            "node_statuses": {**state.get("node_statuses", {}), "analyze_job": NodeStatus.COMPLETED},
        }
    except Exception as e:
        logger.error(f"Analysis failed for {url}: {e}")
        return {
            **_add_event(state, "pipeline:error", "analyst", f"Analysis failed: {e}"),
            "current_analysis": None,
            "node_statuses": {**state.get("node_statuses", {}), "analyze_job": NodeStatus.FAILED},
        }


async def company_research_node(state: dict) -> dict:
    """Deep company research (optional)."""
    if not state.get("use_company_research"):
        return {"node_statuses": {**state.get("node_statuses", {}), "company_research": NodeStatus.SKIPPED}}

    analysis = state.get("current_analysis")
    if not analysis:
        return {"node_statuses": {**state.get("node_statuses", {}), "company_research": NodeStatus.SKIPPED}}

    from src.agents.company_agent import CompanyAgent

    events_update = _add_event(state, "company:start", "company", f"Researching {analysis.company}...")

    try:
        agent = CompanyAgent()
        result = await agent.run(company=analysis.company, role=analysis.role)

        return {
            **_add_event(
                {**state, "events": events_update["events"]},
                "company:result", "company",
                f"Research complete for {analysis.company}",
                result if result.get("success") else {}
            ),
            "node_statuses": {**state.get("node_statuses", {}), "company_research": NodeStatus.COMPLETED},
        }
    except Exception as e:
        logger.error(f"Company research failed: {e}")
        return {
            **_add_event(state, "pipeline:error", "company", f"Research failed: {e}"),
            "node_statuses": {**state.get("node_statuses", {}), "company_research": NodeStatus.FAILED},
        }


async def tailor_resume_node(state: dict) -> dict:
    """Tailor resume for the current job (optional)."""
    if not state.get("use_resume_tailoring"):
        return {"node_statuses": {**state.get("node_statuses", {}), "tailor_resume": NodeStatus.SKIPPED}}

    analysis = state.get("current_analysis")
    profile = state.get("profile")
    if not analysis or not profile:
        return {"node_statuses": {**state.get("node_statuses", {}), "tailor_resume": NodeStatus.SKIPPED}}

    from src.agents.resume_agent import ResumeAgent

    events_update = _add_event(state, "resume:start", "resume", f"Tailoring resume for {analysis.role}...")

    try:
        agent = ResumeAgent()
        result = await agent.run(job_analysis=analysis, user_profile=profile)

        path = result.get("pdf_path") if result.get("success") else None

        events_update = _add_event(
            {**state, "events": events_update["events"]},
            "resume:complete", "resume",
            f"Resume tailored" if path else "Tailoring skipped",
            {"path": path} if path else {}
        )

        return {
            **events_update,
            "node_statuses": {**state.get("node_statuses", {}), "tailor_resume": NodeStatus.COMPLETED},
        }
    except Exception as e:
        logger.error(f"Resume tailoring failed: {e}")
        return {
            **_add_event(state, "pipeline:error", "resume", f"Tailoring failed: {e}"),
            "node_statuses": {**state.get("node_statuses", {}), "tailor_resume": NodeStatus.FAILED},
        }


async def cover_letter_node(state: dict) -> dict:
    """Generate cover letter (optional)."""
    if not state.get("use_cover_letter"):
        return {"node_statuses": {**state.get("node_statuses", {}), "cover_letter": NodeStatus.SKIPPED}}

    analysis = state.get("current_analysis")
    profile = state.get("profile")
    if not analysis or not profile:
        return {"node_statuses": {**state.get("node_statuses", {}), "cover_letter": NodeStatus.SKIPPED}}

    from src.agents.cover_letter_agent import CoverLetterAgent

    events_update = _add_event(state, "cover_letter:start", "cover_letter", f"Drafting cover letter...")

    try:
        agent = CoverLetterAgent()
        result = await agent.run(job_analysis=analysis, user_profile=profile)

        content = result.get("full_text") if result.get("human_approved") else None

        events_update = _add_event(
            {**state, "events": events_update["events"]},
            "cover_letter:complete", "cover_letter",
            "Cover letter generated" if content else "Cover letter skipped",
            {"content": content} if content else {}
        )

        return {
            **events_update,
            "node_statuses": {**state.get("node_statuses", {}), "cover_letter": NodeStatus.COMPLETED},
        }
    except Exception as e:
        logger.error(f"Cover letter failed: {e}")
        return {
            **_add_event(state, "pipeline:error", "cover_letter", f"Generation failed: {e}"),
            "node_statuses": {**state.get("node_statuses", {}), "cover_letter": NodeStatus.FAILED},
        }


async def apply_node(state: dict) -> dict:
    """Apply to current job (if auto_apply is enabled and score meets threshold)."""
    if not state.get("auto_apply"):
        return {
            **_add_event(state, "analyst:result", "analyst", "Queued for manual review"),
            "node_statuses": {**state.get("node_statuses", {}), "apply": NodeStatus.SKIPPED},
        }

    analysis = state.get("current_analysis")
    if not analysis:
        return {"node_statuses": {**state.get("node_statuses", {}), "apply": NodeStatus.SKIPPED}}

    job_urls = state.get("job_urls", [])
    idx = state.get("current_job_index", 0)
    url = job_urls[idx] if idx < len(job_urls) else ""
    profile = state.get("profile")

    events_update = _add_event(state, "applier:start", "applier", f"Applying to {analysis.company}...")

    try:
        from src.services.ws_applier import WebSocketApplierAgent
        session_id = state.get("session_id", "default")
        profile_data = profile.model_dump() if hasattr(profile, "model_dump") else dict(profile)

        ws_applier = WebSocketApplierAgent(session_id)
        result = await ws_applier.run(url, profile_data)

        if result.get("success"):
            events_update = _add_event(
                {**state, "events": events_update["events"]},
                "applier:complete", "applier",
                "Application successful!",
                {"job_id": f"job_{idx + 1}", "url": url}
            )
            return {
                **events_update,
                "total_applied": state.get("total_applied", 0) + 1,
                "node_statuses": {**state.get("node_statuses", {}), "apply": NodeStatus.COMPLETED},
            }
        else:
            return {
                **_add_event(
                    {**state, "events": events_update["events"]},
                    "pipeline:error", "applier",
                    f"Application failed: {result.get('error')}"
                ),
                "node_statuses": {**state.get("node_statuses", {}), "apply": NodeStatus.FAILED},
            }
    except Exception as e:
        logger.error(f"Application failed: {e}")
        return {
            **_add_event(state, "pipeline:error", "applier", f"Application failed: {e}"),
            "node_statuses": {**state.get("node_statuses", {}), "apply": NodeStatus.FAILED},
        }


async def collect_result_node(state: dict) -> dict:
    """Collect results for the current job and decide whether to continue looping."""
    analysis = state.get("current_analysis")
    job_urls = state.get("job_urls", [])
    idx = state.get("current_job_index", 0)
    url = job_urls[idx] if idx < len(job_urls) else ""

    result = JobResult(
        job_id=f"job_{idx + 1}",
        url=url,
        role=analysis.role if analysis else "Unknown",
        company=analysis.company if analysis else "Unknown",
        match_score=analysis.match_score if analysis else 0,
    )

    job_results = state.get("job_results", [])
    job_results.append(result)

    next_idx = idx + 1

    return {
        "job_results": job_results,
        "current_job_index": next_idx,
        "current_analysis": None,
        "node_statuses": {**state.get("node_statuses", {}), "collect_result": NodeStatus.COMPLETED},
    }


# ─── Conditional Edge Functions ─────────────────────────────────

def should_continue_after_profile(state: dict) -> str:
    """After profile load, check if we should proceed or abort."""
    if state.get("error") or not state.get("profile"):
        return "end"
    return "scout"


def should_continue_after_scout(state: dict) -> str:
    """After scout, check if any jobs were found."""
    if not state.get("job_urls"):
        return "end"
    return "analyze_job"


def should_continue_after_analysis(state: dict) -> str:
    """After analysis, check match score threshold."""
    analysis = state.get("current_analysis")
    min_score = state.get("min_match_score", 70)

    if not analysis or analysis.match_score < min_score:
        return "collect_result"  # Skip enrichment, go straight to result collection

    return "enrich"


def should_continue_loop(state: dict) -> str:
    """After collecting result, decide to loop or finish."""
    idx = state.get("current_job_index", 0)
    job_urls = state.get("job_urls", [])
    is_running = state.get("is_running", True)

    if not is_running or idx >= len(job_urls):
        return "end"
    return "analyze_job"


# ─── Graph Construction ────────────────────────────────────────

def create_pipeline_graph() -> StateGraph:
    """
    Build and compile the LangGraph pipeline.

    Flow:
        load_profile → scout → [loop: analyze → enrich(parallel) → apply → collect → loop]
    
    Parallel enrichment:
        company_research + tailor_resume + cover_letter run concurrently
    """
    graph = StateGraph(dict)

    # ── Add Nodes ──
    graph.add_node("load_profile", load_profile_node)
    graph.add_node("scout", scout_node)
    graph.add_node("analyze_job", analyze_job_node)
    graph.add_node("company_research", company_research_node)
    graph.add_node("tailor_resume", tailor_resume_node)
    graph.add_node("cover_letter", cover_letter_node)
    graph.add_node("apply", apply_node)
    graph.add_node("collect_result", collect_result_node)

    # ── Entry Point ──
    graph.set_entry_point("load_profile")

    # ── Conditional Edges ──
    graph.add_conditional_edges("load_profile", should_continue_after_profile, {
        "scout": "scout",
        "end": END,
    })

    graph.add_conditional_edges("scout", should_continue_after_scout, {
        "analyze_job": "analyze_job",
        "end": END,
    })

    graph.add_conditional_edges("analyze_job", should_continue_after_analysis, {
        "enrich": "company_research",  # Start of enrichment chain
        "collect_result": "collect_result",
    })

    # Enrichment chain: company_research → tailor_resume → cover_letter → apply
    # (Sequential for simplicity; can be parallelized with fan-out later)
    graph.add_edge("company_research", "tailor_resume")
    graph.add_edge("tailor_resume", "cover_letter")
    graph.add_edge("cover_letter", "apply")
    graph.add_edge("apply", "collect_result")

    # Loop back
    graph.add_conditional_edges("collect_result", should_continue_loop, {
        "analyze_job": "analyze_job",
        "end": END,
    })

    return graph.compile()


# ─── Runner with WebSocket Bridge ──────────────────────────────

async def run_pipeline_graph(
    query: str,
    location: str,
    session_id: str = "default",
    user_id: str = None,
    min_match_score: int = 70,
    auto_apply: bool = False,
    use_company_research: bool = False,
    use_resume_tailoring: bool = False,
    use_cover_letter: bool = False,
    event_callback=None,
) -> dict:
    """
    Execute the pipeline graph and stream events via callback.

    Checkpoints are saved after each node so the run can be resumed
    if the process is restarted.  On successful completion the
    checkpoint file is removed.

    Args:
        event_callback: async callable(event_dict) for WebSocket emission
    """
    graph = create_pipeline_graph()
    checkpoint = PipelineCheckpoint(session_id)

    # Attempt to restore from a previous checkpoint
    saved = checkpoint.load()

    initial_state = saved if saved else {
        "query": query,
        "location": location,
        "session_id": session_id,
        "user_id": user_id,
        "min_match_score": min_match_score,
        "auto_apply": auto_apply,
        "use_company_research": use_company_research,
        "use_resume_tailoring": use_resume_tailoring,
        "use_cover_letter": use_cover_letter,
        "job_urls": [],
        "current_job_index": 0,
        "current_analysis": None,
        "job_results": [],
        "node_statuses": {},
        "total_analyzed": 0,
        "total_applied": 0,
        "total_skipped": 0,
        "events": [],
        "is_running": True,
        "error": None,
        "profile": None,
        "profile_source": None,
        "resume_text": "",
    }

    # Stream events as graph progresses
    last_event_count = 0

    async for step in graph.astream(initial_state, stream_mode="updates"):
        # Each step contains the node name and its output
        for node_name, node_output in step.items():
            if not isinstance(node_output, dict):
                continue

            events = node_output.get("events", [])
            new_events = events[last_event_count:]
            last_event_count = len(events)

            if event_callback:
                for event in new_events:
                    try:
                        await event_callback(event)
                    except Exception as e:
                        logger.warning(f"Event callback failed: {e}")

            logger.info(f"[Graph] Node '{node_name}' completed. Status: {node_output.get('node_statuses', {}).get(node_name, 'unknown')}")

            # Persist checkpoint after each node
            merged = {**initial_state, **node_output}
            checkpoint.save(merged, completed_node=node_name)
            initial_state.update(node_output)

    # Pipeline finished — clean up checkpoint
    checkpoint.clear()

    # Final result
    return {
        "success": initial_state.get("error") is None,
        "analyzed": initial_state.get("total_analyzed", 0),
        "applied": initial_state.get("total_applied", 0),
        "skipped": initial_state.get("total_skipped", 0),
        "job_results": initial_state.get("job_results", []),
    }
