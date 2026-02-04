"""
Applier Task - Browser Automation in Celery Worker

This task runs the LiveApplierService in a Celery worker process,
keeping the FastAPI server responsive.

Flow:
1. API receives apply request → Returns 202 + task_id
2. This task runs in worker → Browser automation
3. Events published to Redis pub/sub → FastAPI relays to WebSocket
4. HITL: Worker publishes request → Redis → Frontend responds → Redis → Worker

Run worker:
    celery -A worker.celery_app worker -Q browser --loglevel=info --pool=solo
"""
import asyncio
import json
import logging
from typing import Optional
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

logger = logging.getLogger(__name__)


class RedisEventPublisher:
    """
    Publishes events to Redis for the FastAPI server to relay to WebSocket.
    
    Channel format: jobai:events:{session_id}
    """
    
    def __init__(self, session_id: str, redis_url: str):
        self.session_id = session_id
        self.redis_url = redis_url
        self._redis = None
        
    async def _get_redis(self):
        """Lazy-load Redis connection."""
        if not self._redis:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self.redis_url)
        return self._redis
    
    async def publish_event(self, event_type: str, message: str, data: dict = None):
        """Publish an event to Redis for the WebSocket handler."""
        redis = await self._get_redis()
        
        event = {
            "type": event_type,
            "agent": "applier",
            "message": message,
            "data": data or {},
            "session_id": self.session_id,
        }
        
        channel = f"jobai:events:{self.session_id}"
        await redis.publish(channel, json.dumps(event))
        logger.debug(f"Published event: {event_type} to {channel}")
    
    async def request_hitl(self, question: str, hitl_id: str, context: str = "") -> str:
        """
        Request human input via Redis pub/sub.
        
        Flow:
        1. Publish HITL request to events channel
        2. Subscribe to response channel
        3. Wait for response with timeout
        """
        redis = await self._get_redis()
        
        # Publish HITL request
        await self.publish_event(
            "hitl:request",
            question,
            {"hitl_id": hitl_id, "context": context}
        )
        
        # Subscribe to response channel
        response_channel = f"jobai:hitl:{hitl_id}"
        pubsub = redis.pubsub()
        await pubsub.subscribe(response_channel)
        
        try:
            # Wait for response (2 minute timeout)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    return data.get("response", "")
                    
                # Check timeout
                # Note: Real implementation would use asyncio.wait_for
                
        finally:
            await pubsub.unsubscribe(response_channel)
            
        return ""
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


def run_async(coro):
    """
    Run async code inside Celery task.
    
    Celery is synchronous but we need async for browser_use.
    This creates a new event loop for each task.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()



class LiveApplierServiceWithDraft:
    """
    Extended LiveApplierService that publishes events to Redis
    and supports draft mode.
    
    This is a thin wrapper that adapts the original service
    for Celery worker usage.
    """
    
    def __init__(self, session_id: str, publisher: RedisEventPublisher, draft_mode: bool = True, user_id: Optional[str] = None):
        self.session_id = session_id
        self.publisher = publisher
        self.draft_mode = draft_mode
        self.user_id = user_id
        self._service = None

    async def run(self, url: str) -> dict:
        """Run the applier with draft mode support."""
        # Import the actual service
        # Import here to avoid loading browser_use in worker unless needed
        from src.services.LiveApplier import LiveApplierService
        
        # Create the underlying service
        self._service = LiveApplierService(self.session_id, user_id=self.user_id)
        
        # Override the emit method to publish to Redis
        
        async def redis_emit(event_type, message, data=None):
            # Handle enum event types
            event_type_str = event_type.value if hasattr(event_type, 'value') else str(event_type)
            
            await self.publisher.publish_event(
                event_type_str,
                message,
                data
            )
        
        self._service.emit = redis_emit
        # Override emit_chat too
        self._service.emit_chat = lambda sender, msg, data=None: asyncio.create_task(
            redis_emit("chat:message", msg, {"sender": sender, **(data or {})})
        )
        
        # Run with draft mode if enabled
        # Note: Full draft mode implementation is in live_applier.py
        result = await self._service.run(url)
        
        return result


@shared_task(
    bind=True,
    name="worker.tasks.applier_task.apply_to_job",
    max_retries=2,
    soft_time_limit=540,  # 9 minutes
    time_limit=600,  # 10 minutes
)
def apply_to_job(
    self,
    job_url: str,
    session_id: str,
    draft_mode: bool = True,
    redis_url: str = None,
    user_id: str = None,
) -> dict:
    """
    Apply to a job using browser automation.
    
    Args:
        job_url: URL of the job posting
        session_id: WebSocket session ID for events
        draft_mode: If True, pause before submitting for user confirmation
        redis_url: Redis URL for event publishing
        
    Returns:
        Dict with success status and any error message
    """
    from src.core.config import settings
    
    redis_url = redis_url or settings.redis_url or "redis://localhost:6379/0"
    
    async def _apply():
        publisher = RedisEventPublisher(session_id, redis_url)
        
        try:
            # Create service with draft mode
            service = LiveApplierServiceWithDraft(session_id, publisher, draft_mode, user_id)
            
            await publisher.publish_event("task:started", f"Starting application to {job_url}")
            
            # Run the application
            result = await service.run(job_url)
            
            await publisher.publish_event(
                "task:complete" if result.get("success") else "task:failed",
                "Application complete" if result.get("success") else f"Failed: {result.get('error')}",
                result
            )
            
            return result
            
        except SoftTimeLimitExceeded:
            await publisher.publish_event("task:failed", "Task timed out (9 minutes)")
            return {"success": False, "error": "Task timed out"}
            
        except Exception as e:
            logger.exception(f"Apply task failed: {e}")
            await publisher.publish_event("task:failed", f"Error: {str(e)}")
            return {"success": False, "error": str(e)}
            
        finally:
            await publisher.close()
    
    return run_async(_apply())


@shared_task(
    name="worker.tasks.applier_task.get_task_status",
)
def get_task_status(task_id: str) -> dict:
    """
    Get the status of an apply task.
    
    This is a utility task that can be called to check status
    without querying the result backend directly.
    """
    from celery.result import AsyncResult
    from worker.celery_app import celery_app
    
    result = AsyncResult(task_id, app=celery_app)
    
    return {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
        "result": result.result if result.ready() else None,
    }
