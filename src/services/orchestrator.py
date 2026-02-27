"""
Pipeline Orchestrator with LangGraph State Machine + Event Streaming

Uses LangGraph StateGraph for the pipeline flow while preserving
the original WebSocket event emission pattern.

Architecture:
  - LangGraph handles node orchestration, conditional edges, and state management
  - Events are emitted to WebSocket via event_callback bridge
  - Event Bus publishes pipeline lifecycle events for decoupled consumers
  - Guardrails validate user inputs before pipeline execution
"""
import asyncio
import sys
import os
import logging
from typing import Optional, Callable, Any
from datetime import datetime

from src.api.websocket import EventEmitter, EventType, manager, AgentEvent

logger = logging.getLogger(__name__)


class StreamingPipelineOrchestrator:
    """
    Orchestrates the job application pipeline using LangGraph StateGraph.
    Events are streamed to WebSocket clients in real-time.
    Event Bus emits lifecycle events for decoupled consumers.
    Supports multi-user via user_id for per-user profile loading.
    """
    
    def __init__(self, session_id: str = "default", user_id: Optional[str] = None):
        self.session_id = session_id
        self.user_id = user_id
        self._manager = manager
        self._is_running = True
        
        # Lazy-load event bus (optional dependency)
        self._event_bus = None
        try:
            from src.core.event_bus import event_bus
            self._event_bus = event_bus
        except ImportError:
            pass
    
    async def emit(self, event_type: EventType, agent: str, message: str, data: dict = None):
        """Emit an event to connected clients AND event bus."""
        event = AgentEvent(
            type=event_type,
            agent=agent,
            message=message,
            data=data or {}
        )
        await self._manager.send_event(self.session_id, event)
        
        # Also publish to event bus for decoupled consumers
        if self._event_bus:
            try:
                await self._event_bus.emit(f"pipeline:{event_type.value}", {
                    "session_id": self.session_id,
                    "user_id": self.user_id,
                    "agent": agent,
                    "message": message,
                    "data": data or {},
                    "timestamp": datetime.now().isoformat(),
                })
            except Exception as e:
                logger.debug(f"Event bus publish error (non-fatal): {e}")
    
    def stop(self):
        """Stop the pipeline."""
        self._is_running = False
    
    async def _event_bridge(self, event_dict: dict):
        """
        Bridge LangGraph events to WebSocket.
        Converts graph event dicts to AgentEvent and sends via WebSocket.
        """
        try:
            event_type_str = event_dict.get("type", "")
            # Map string event types to EventType enum
            try:
                event_type = EventType(event_type_str)
            except ValueError:
                event_type = EventType.PIPELINE_ERROR
            
            await self.emit(
                event_type,
                event_dict.get("agent", "system"),
                event_dict.get("message", ""),
                event_dict.get("data", {})
            )
        except Exception as e:
            logger.warning(f"Event bridge error: {e}")

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
        Run the full pipeline using LangGraph StateGraph.
        
        The graph handles:
          - Profile loading (DB → YAML fallback)
          - Job scouting via search engines
          - Per-job analysis with match scoring
          - Conditional enrichment (company research, resume tailoring, cover letter)
          - Optional auto-apply with browser automation
          - Result collection and loop control
        
        Events are streamed via WebSocket in real-time.
        """
        # Validate input with guardrails (non-blocking)
        try:
            from src.core.guardrails import create_input_pipeline, GuardrailAction
            pipeline = create_input_pipeline()
            result = await pipeline.process(query)
            if result.action == GuardrailAction.BLOCK:
                await self.emit(
                    EventType.PIPELINE_ERROR,
                    "guardrails",
                    f"Input blocked by safety guardrails: {result.reason}",
                    {"blocked": True, "reason": result.reason}
                )
                return {"success": False, "error": f"Input blocked: {result.reason}"}
            # Use sanitized query if modified
            if result.modified_content:
                query = result.modified_content
        except ImportError:
            pass  # Guardrails not available, skip
        except Exception as e:
            logger.warning(f"Guardrail check failed (non-blocking): {e}")
        
        await self.emit(
            EventType.PIPELINE_START,
            "system",
            f"Starting LangGraph pipeline for '{query}' in '{location}'",
            {
                "query": query, "location": location, "auto_apply": auto_apply,
                "user_id": self.user_id,
                "engine": "langgraph",
                "options": {
                    "research": use_company_research,
                    "tailor": use_resume_tailoring,
                    "cover_letter": use_cover_letter
                }
            }
        )
        
        try:
            from src.graphs.pipeline_graph import run_pipeline_graph
            
            result = await run_pipeline_graph(
                query=query,
                location=location,
                session_id=self.session_id,
                user_id=self.user_id,
                min_match_score=min_match_score,
                auto_apply=auto_apply,
                use_company_research=use_company_research,
                use_resume_tailoring=use_resume_tailoring,
                use_cover_letter=use_cover_letter,
                event_callback=self._event_bridge,
            )
            
            await self.emit(
                EventType.PIPELINE_COMPLETE,
                "system",
                f"LangGraph pipeline finished. Applied to {result.get('applied', 0)} jobs.",
                {
                    "analyzed": result.get("analyzed", 0),
                    "applied": result.get("applied", 0),
                    "engine": "langgraph",
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"LangGraph pipeline failed: {e}", exc_info=True)
            await self.emit(
                EventType.PIPELINE_ERROR,
                "system",
                f"Pipeline failed: {str(e)}",
                {"error": str(e)}
            )
            return {"success": False, "error": str(e)}
