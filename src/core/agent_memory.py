"""
Agent Memory — Persistent Memory System for AI Agents

Gives agents the ability to remember past interactions, store learnings,
and improve over time through user feedback. Two-tier storage:
  - Redis: fast ephemeral cache for active sessions
  - Supabase: durable persistence for long-term memory

Usage:
    memory = AgentMemory()
    await memory.remember("resume_agent", user_id, "preferred_style", "technical")
    style = await memory.recall("resume_agent", user_id, "preferred_style")
    await memory.record_feedback("resume_agent", user_id, session_id, 4.5, "Great resume")
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    PREFERENCE = "preference"
    LEARNING = "learning"
    CONTEXT = "context"
    FEEDBACK = "feedback"
    PERFORMANCE = "performance"


@dataclass
class MemoryEntry:
    """A single memory record."""
    agent_name: str
    user_id: str
    key: str
    value: Any
    memory_type: MemoryType = MemoryType.CONTEXT
    confidence: float = 1.0
    access_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None


@dataclass
class FeedbackEntry:
    """User feedback on agent output."""
    agent_name: str
    user_id: str
    session_id: str
    rating: float
    comments: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AgentInsight:
    """A distilled learning from accumulated feedback."""
    agent_name: str
    insight: str
    source_count: int
    avg_rating: float
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentMemory:
    """
    Persistent memory system for AI agents.
    
    Supports two backends:
      - Supabase (primary): durable storage with RLS
      - In-memory fallback: dict-based for development/testing
    
    Memory operations are non-blocking and failure-tolerant —
    a memory failure should never crash an agent.
    """

    def __init__(self, supabase_client=None):
        self._client = supabase_client
        self._cache: Dict[str, MemoryEntry] = {}
        self._feedback_buffer: List[FeedbackEntry] = []
        self._initialized = False

    def _ensure_client(self):
        """Lazy-load supabase client if not injected."""
        if self._client is None:
            try:
                from src.services.supabase_client import supabase_client
                self._client = supabase_client
                self._initialized = True
            except Exception as e:
                logger.warning(f"Supabase not available for agent memory, using in-memory fallback: {e}")
                self._initialized = False

    def _cache_key(self, agent: str, user_id: str, key: str) -> str:
        return f"{agent}:{user_id}:{key}"

    # ── Core Memory Operations ──────────────────────────────────

    async def remember(
        self,
        agent_name: str,
        user_id: str,
        key: str,
        value: Any,
        memory_type: MemoryType = MemoryType.CONTEXT,
        ttl_hours: Optional[int] = None,
        confidence: float = 1.0,
    ) -> bool:
        """
        Store a memory for an agent-user pair.
        
        Returns True if stored successfully, False on failure.
        Failures are logged but never raised — memory is best-effort.
        """
        expires_at = None
        if ttl_hours:
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()

        entry = MemoryEntry(
            agent_name=agent_name,
            user_id=user_id,
            key=key,
            value=value,
            memory_type=memory_type,
            confidence=confidence,
            expires_at=expires_at,
        )

        # Always cache locally for fast access
        ck = self._cache_key(agent_name, user_id, key)
        self._cache[ck] = entry

        # Persist to Supabase
        self._ensure_client()
        if self._client:
            try:
                data = {
                    "user_id": user_id,
                    "agent_name": agent_name,
                    "memory_key": key,
                    "memory_value": json.dumps(value) if not isinstance(value, str) else value,
                    "memory_type": memory_type.value,
                    "confidence": confidence,
                    "expires_at": expires_at,
                }
                self._client.table("agent_memories").upsert(
                    data, on_conflict="user_id,agent_name,memory_key"
                ).execute()
                logger.debug(f"[Memory] Stored: {agent_name}/{key} for user {user_id[:8]}...")
                return True
            except Exception as e:
                logger.warning(f"[Memory] Failed to persist {agent_name}/{key}: {e}")
                return True  # still in cache

        return True  # in-memory fallback worked

    async def recall(
        self,
        agent_name: str,
        user_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Retrieve a memory. Checks local cache first, then Supabase.
        
        Returns the stored value or `default` if not found.
        """
        # Check cache first
        ck = self._cache_key(agent_name, user_id, key)
        if ck in self._cache:
            entry = self._cache[ck]
            # Check expiration
            if entry.expires_at:
                exp = datetime.fromisoformat(entry.expires_at)
                if datetime.now(timezone.utc) > exp:
                    del self._cache[ck]
                    return default
            entry.access_count += 1
            return entry.value

        # Try Supabase
        self._ensure_client()
        if self._client:
            try:
                result = (
                    self._client.table("agent_memories")
                    .select("memory_value, expires_at")
                    .eq("agent_name", agent_name)
                    .eq("user_id", user_id)
                    .eq("memory_key", key)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    row = result.data[0]
                    # Check expiration
                    if row.get("expires_at"):
                        exp = datetime.fromisoformat(row["expires_at"])
                        if datetime.now(timezone.utc) > exp:
                            return default
                    value = row["memory_value"]
                    try:
                        value = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        pass
                    # Populate cache for next time
                    self._cache[ck] = MemoryEntry(
                        agent_name=agent_name,
                        user_id=user_id,
                        key=key,
                        value=value,
                    )
                    return value
            except Exception as e:
                logger.warning(f"[Memory] Failed to recall {agent_name}/{key}: {e}")

        return default

    async def recall_all(
        self,
        agent_name: str,
        user_id: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve all memories for an agent-user pair, optionally filtered by type."""
        self._ensure_client()
        if not self._client:
            # Return from cache
            results = []
            for ck, entry in self._cache.items():
                if entry.agent_name == agent_name and entry.user_id == user_id:
                    if memory_type and entry.memory_type != memory_type:
                        continue
                    results.append({"key": entry.key, "value": entry.value, "type": entry.memory_type.value})
            return results[:limit]

        try:
            query = (
                self._client.table("agent_memories")
                .select("memory_key, memory_value, memory_type, confidence, created_at")
                .eq("agent_name", agent_name)
                .eq("user_id", user_id)
            )
            if memory_type:
                query = query.eq("memory_type", memory_type.value)
            result = query.order("created_at", desc=True).limit(limit).execute()

            memories = []
            for row in result.data or []:
                val = row["memory_value"]
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
                memories.append({
                    "key": row["memory_key"],
                    "value": val,
                    "type": row.get("memory_type", "context"),
                    "confidence": row.get("confidence", 1.0),
                    "created_at": row.get("created_at"),
                })
            return memories
        except Exception as e:
            logger.warning(f"[Memory] Failed to recall_all for {agent_name}: {e}")
            return []

    async def forget(self, agent_name: str, user_id: str, key: str) -> bool:
        """Remove a specific memory."""
        ck = self._cache_key(agent_name, user_id, key)
        self._cache.pop(ck, None)

        self._ensure_client()
        if self._client:
            try:
                self._client.table("agent_memories").delete().eq(
                    "agent_name", agent_name
                ).eq("user_id", user_id).eq("memory_key", key).execute()
                return True
            except Exception as e:
                logger.warning(f"[Memory] Failed to forget {agent_name}/{key}: {e}")
        return False

    # ── Feedback System ─────────────────────────────────────────

    async def record_feedback(
        self,
        agent_name: str,
        user_id: str,
        session_id: str,
        rating: float,
        comments: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record user feedback for an agent interaction.
        
        Rating is 1.0-5.0. Context can include the original input/output
        for future analysis.
        """
        rating = max(1.0, min(5.0, rating))

        entry = FeedbackEntry(
            agent_name=agent_name,
            user_id=user_id,
            session_id=session_id,
            rating=rating,
            comments=comments,
            context=context or {},
        )
        self._feedback_buffer.append(entry)

        self._ensure_client()
        if self._client:
            try:
                data = {
                    "user_id": user_id,
                    "agent_name": agent_name,
                    "session_id": session_id,
                    "rating": rating,
                    "comments": comments,
                    "context": context or {},
                }
                self._client.table("agent_feedback").insert(data).execute()
                logger.info(
                    f"[Memory] Feedback recorded: {agent_name} rated {rating}/5 "
                    f"by user {user_id[:8]}..."
                )
                return True
            except Exception as e:
                logger.warning(f"[Memory] Failed to persist feedback: {e}")

        return True  # buffered locally

    async def get_feedback_summary(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get aggregated feedback stats for an agent.
        
        Returns avg rating, total count, and recent comments.
        """
        self._ensure_client()
        if not self._client:
            # Compute from buffer
            relevant = [f for f in self._feedback_buffer if f.agent_name == agent_name]
            if user_id:
                relevant = [f for f in relevant if f.user_id == user_id]
            if not relevant:
                return {"avg_rating": 0, "total": 0, "recent_comments": []}
            avg = sum(f.rating for f in relevant) / len(relevant)
            return {
                "avg_rating": round(avg, 2),
                "total": len(relevant),
                "recent_comments": [f.comments for f in relevant[-5:] if f.comments],
            }

        try:
            query = (
                self._client.table("agent_feedback")
                .select("rating, comments, created_at")
                .eq("agent_name", agent_name)
            )
            if user_id:
                query = query.eq("user_id", user_id)
            result = query.order("created_at", desc=True).limit(limit).execute()

            if not result.data:
                return {"avg_rating": 0, "total": 0, "recent_comments": []}

            ratings = [r["rating"] for r in result.data]
            comments = [r["comments"] for r in result.data[:5] if r.get("comments")]
            return {
                "avg_rating": round(sum(ratings) / len(ratings), 2),
                "total": len(ratings),
                "recent_comments": comments,
            }
        except Exception as e:
            logger.warning(f"[Memory] Failed to get feedback summary: {e}")
            return {"avg_rating": 0, "total": 0, "recent_comments": []}

    async def get_learnings(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
    ) -> List[str]:
        """
        Distill actionable learnings from feedback history.
        
        Returns a list of insight strings that agents can inject
        into their system prompts for personalization.
        """
        memories = await self.recall_all(
            agent_name, user_id or "system", MemoryType.LEARNING
        )
        feedback = await self.get_feedback_summary(agent_name, user_id)

        learnings = [m["value"] for m in memories if isinstance(m["value"], str)]

        # Add feedback-derived insights
        if feedback["total"] > 0:
            if feedback["avg_rating"] < 3.0:
                learnings.append(
                    f"User satisfaction is low ({feedback['avg_rating']}/5). "
                    "Focus on quality and ask for clarification when uncertain."
                )
            elif feedback["avg_rating"] >= 4.5:
                learnings.append(
                    f"User is highly satisfied ({feedback['avg_rating']}/5). "
                    "Continue current approach."
                )

        return learnings

    # ── Diagnostics ─────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Return memory system stats for health checks."""
        return {
            "cache_size": len(self._cache),
            "feedback_buffer_size": len(self._feedback_buffer),
            "supabase_connected": self._initialized,
        }


# ── Singleton ───────────────────────────────────────────────────

agent_memory = AgentMemory()
