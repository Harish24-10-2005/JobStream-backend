"""
Pipeline API Routes
"""

import logging
import hashlib
import time
import uuid
from typing import TYPE_CHECKING, Annotated, Dict, Optional

if TYPE_CHECKING:
	from src.services.orchestrator import StreamingPipelineOrchestrator

from fastapi import APIRouter, Depends, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, field_validator

from src.api.schemas import HITLResponse, PipelineActionResponse, PipelineStartResponse, PipelineStatusResponse
from src.api.websocket import AgentEvent, EventType, manager
from src.core.auth import AuthUser, get_current_user
from src.core.config import settings
from src.core.distributed_lock import distributed_lock_manager
from src.core.idempotency import idempotency_store
from src.services.user_profile_service import user_profile_service

router = APIRouter()
logger = logging.getLogger(__name__)


class PipelineConfig(BaseModel):
	query: str
	location: str = 'Remote'
	auto_apply: bool = True
	min_match_score: int = 70
	max_jobs: int = 10
	session_id: Optional[str] = None
	# Per-step overrides: None = let the planner decide, True/False = force
	use_resume_tailoring: Optional[bool] = None
	use_cover_letter: Optional[bool] = None
	use_company_research: Optional[bool] = None

	@field_validator('query')
	@classmethod
	def validate_query(cls, value: str) -> str:
		q = (value or '').strip()
		if q.lower().startswith('apply for '):
			q = q[10:].strip()
		if len(q) < 2:
			raise ValueError('query must contain at least 2 characters')
		return q

	@field_validator('location')
	@classmethod
	def normalize_location(cls, value: str) -> str:
		loc = (value or '').strip()
		return loc or 'Remote'

	@field_validator('max_jobs')
	@classmethod
	def validate_max_jobs(cls, value: int) -> int:
		return max(1, min(int(value), 50))


class PipelineStatus(BaseModel):
	running: bool
	current_agent: Optional[str] = None
	progress: int
	jobs_found: int
	jobs_applied: int


# Try to import Redis, but provide fallback
try:
	from src.core.redis_client import get_redis_client

	REDIS_AVAILABLE = True
except ImportError:
	REDIS_AVAILABLE = False

# In-memory fallback store (for development without Redis)
_memory_store: Dict[str, dict] = {}
_redis_unavailable_until = 0.0
_REDIS_RETRY_SECONDS = 30.0


def _get_default_state() -> dict:
	"""Return default pipeline state."""
	return {'running': False, 'current_agent': None, 'progress': 0, 'jobs_found': 0, 'jobs_applied': 0}


async def _check_redis_connection() -> bool:
	"""Check if Redis is available."""
	if not REDIS_AVAILABLE:
		return False
	global _redis_unavailable_until
	if _redis_unavailable_until > time.time():
		return False
	try:
		redis = get_redis_client()
		await redis.ping()
		return True
	except Exception:
		_redis_unavailable_until = time.time() + _REDIS_RETRY_SECONDS
		return False


async def get_pipeline_state(user_id: str) -> dict:
	"""Get or initialize state for a user. Uses Redis if available, otherwise in-memory."""

	# Try Redis first
	if REDIS_AVAILABLE:
		global _redis_unavailable_until
		if _redis_unavailable_until > time.time():
			# Temporary circuit-breaker while Redis is down.
			pass
		else:
			try:
				redis = get_redis_client()
				key = f'pipeline:{user_id}:state'

				# Get all fields
				state = await redis.hgetall(key)

				if not state:
					# Initialize default state in Redis
					initial_state = {'running': '0', 'current_agent': 'None', 'progress': '0', 'jobs_found': '0', 'jobs_applied': '0'}
					await redis.hset(key, mapping=initial_state)
					await redis.expire(key, 86400)
					return _get_default_state()

				# Convert types (Redis stores everything as strings)
				return {
					'running': state.get('running', '0') == '1',
					'current_agent': None if state.get('current_agent') == 'None' else state.get('current_agent'),
					'progress': int(state.get('progress', 0)),
					'jobs_found': int(state.get('jobs_found', 0)),
					'jobs_applied': int(state.get('jobs_applied', 0)),
				}
			except Exception as e:
				_redis_unavailable_until = time.time() + _REDIS_RETRY_SECONDS
				logger.warning(f'Redis Error (falling back to memory for {_REDIS_RETRY_SECONDS:.0f}s): {e}')
				# Fall through to memory store

	# In-memory fallback
	if settings.is_production:
		raise HTTPException(status_code=503, detail='Pipeline state backend unavailable')
	if user_id not in _memory_store:
		_memory_store[user_id] = _get_default_state()
	return _memory_store[user_id].copy()


async def update_pipeline_state(user_id: str, updates: dict):
	"""Update specific fields in state. Uses Redis if available, otherwise in-memory."""

	# Try Redis first
	if REDIS_AVAILABLE:
		global _redis_unavailable_until
		if _redis_unavailable_until <= time.time():
			try:
				redis = get_redis_client()
				key = f'pipeline:{user_id}:state'

				# Convert booleans to 1/0 and None to literal "None"
				redis_updates = {}
				for k, v in updates.items():
					if isinstance(v, bool):
						redis_updates[k] = '1' if v else '0'
					elif v is None:
						redis_updates[k] = 'None'
					else:
						redis_updates[k] = str(v)

				await redis.hset(key, mapping=redis_updates)
				return
			except Exception as e:
				_redis_unavailable_until = time.time() + _REDIS_RETRY_SECONDS
				logger.warning(f'Redis Update Error (falling back to memory for {_REDIS_RETRY_SECONDS:.0f}s): {e}')
				# Fall through to memory store

	# In-memory fallback
	if settings.is_production:
		raise HTTPException(status_code=503, detail='Pipeline state backend unavailable')
	if user_id not in _memory_store:
		_memory_store[user_id] = _get_default_state()
	_memory_store[user_id].update(updates)


@router.get('/status', response_model=PipelineStatusResponse)
async def get_pipeline_status(user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Get current pipeline status for the authenticated user.
	"""
	return await get_pipeline_state(user.id)


# Store active orchestrators for stop functionality
_active_orchestrators: Dict[str, 'StreamingPipelineOrchestrator'] = {}


async def _run_pipeline_task(user_id: str, session_id: str, config: dict):
	"""Background task that runs the pipeline orchestrator."""
	from src.services.orchestrator import StreamingPipelineOrchestrator

	try:
		orchestrator = StreamingPipelineOrchestrator(session_id=session_id, user_id=user_id)
		_active_orchestrators[user_id] = orchestrator
		progress_map = {
			'planning': 5,
			'scout': 20,
			'analyst': 40,
			'company': 55,
			'resume': 70,
			'cover_letter': 85,
			'applier': 95,
		}
		runtime_applied = 0

		async def sync_status(event: dict):
			nonlocal runtime_applied
			event_type = str(event.get('type', ''))
			agent = str(event.get('agent', '') or 'system')
			data = event.get('data', {}) or {}
			updates = {}

			if event_type.endswith(':start'):
				updates['running'] = True
				updates['current_agent'] = agent
				updates['progress'] = progress_map.get(agent, 10)
			elif event_type == 'scout:complete':
				updates['jobs_found'] = int(data.get('count', 0))
				updates['current_agent'] = 'scout'
				updates['progress'] = 30
			elif event_type == 'analyst:result':
				updates['current_agent'] = 'analyst'
				updates['progress'] = 50
			elif event_type == 'resume:complete':
				updates['current_agent'] = 'resume'
				updates['progress'] = 75
			elif event_type == 'cover_letter:complete':
				updates['current_agent'] = 'cover_letter'
				updates['progress'] = 88
			elif event_type == 'applier:complete':
				runtime_applied += 1
				updates['current_agent'] = 'applier'
				updates['jobs_applied'] = runtime_applied
				updates['progress'] = 96
			elif event_type in ('pipeline:complete', 'pipeline:error'):
				updates['running'] = False
				updates['current_agent'] = None
				updates['progress'] = 100 if event_type == 'pipeline:complete' else 0

			if updates:
				await update_pipeline_state(user_id, updates)

		orchestrator.set_status_callback(sync_status)

		result = await orchestrator.run(
			query=config['query'],
			location=config['location'],
			min_match_score=config['min_match_score'],
			max_jobs=config.get('max_jobs', 10),
			auto_apply=config['auto_apply'],
			use_resume_tailoring=config.get('use_resume_tailoring'),
			use_cover_letter=config.get('use_cover_letter'),
			use_company_research=config.get('use_company_research'),
		)
		await update_pipeline_state(
			user_id,
			{
				'running': False,
				'current_agent': None,
				'progress': 100 if result and result.get('success') else 0,
				'jobs_applied': int(result.get('applied', runtime_applied)) if isinstance(result, dict) else runtime_applied,
			},
		)
	except Exception as e:
		logger.error(f'Pipeline error for user {user_id}: {e}')
		await update_pipeline_state(user_id, {'running': False, 'current_agent': None, 'progress': 0})
	finally:
		if user_id in _active_orchestrators:
			del _active_orchestrators[user_id]


from fastapi import BackgroundTasks


@router.post('/start', response_model=PipelineStartResponse)
async def start_pipeline(
	config: PipelineConfig,
	background_tasks: BackgroundTasks,
	user: Annotated[AuthUser, Depends(get_current_user)],
	idempotency_key: Annotated[Optional[str], Header(alias='Idempotency-Key')] = None,
):
	"""
	Start the agentic pipeline for the authenticated user.
	Runs Scout → Analyst → Resume → Cover Letter → Applier in background.

	Safety:
	  - Distributed lock prevents concurrent starts for the same user.
	  - Idempotency key (auto-generated from user_id if absent) prevents
	    duplicate pipelines from frontend retries.
	  - Running state is checked *inside* the lock to avoid TOCTOU races.
	"""
	# ── Idempotency: honour explicit key or auto-generate a short-lived one
	if idempotency_key:
		_idem_key = idempotency_key
	else:
		config_fingerprint = hashlib.sha256(
			(
				f'{config.query}|{config.location}|{config.auto_apply}|{config.min_match_score}|'
				f'{config.max_jobs}|{config.use_resume_tailoring}|{config.use_cover_letter}|'
				f'{config.use_company_research}'
			).encode('utf-8')
		).hexdigest()[:16]
		_idem_key = f'auto:{user.id}:{config_fingerprint}:{int(time.time()) // 10}'
	idempotency_lookup = f'pipeline:start:{user.id}:{_idem_key}'
	cached = await idempotency_store.get(idempotency_lookup)
	if cached:
		return cached.response

	# ── Distributed lock: serialise concurrent start requests per-user
	lock_key = f'pipeline:start:{user.id}'
	lock_token = await distributed_lock_manager.acquire(lock_key, ttl_seconds=30)
	if not lock_token:
		raise HTTPException(status_code=409, detail='Pipeline start is already in progress. Please retry.')

	try:
		# Check running state *inside* lock to prevent TOCTOU races
		state = await get_pipeline_state(user.id)

		if state['running']:
			raise HTTPException(status_code=400, detail='Pipeline is already running')

		# Enforce profile + resume readiness before running expensive pipeline.
		completion = await user_profile_service.get_profile_completion(user.id)
		missing = []
		if not completion.get('has_profile'):
			missing.append('profile')
		if not completion.get('has_resume'):
			missing.append('resume')
		if not completion.get('has_skills'):
			missing.append('skills')
		if not (completion.get('has_experience') or completion.get('has_projects') or completion.get('has_education')):
			missing.append('experience_or_projects_or_education')
		if missing:
			raise HTTPException(
				status_code=422,
				detail={
					'message': 'Profile is incomplete. Upload resume and complete required details before launching pipeline.',
					'missing_requirements': missing,
					'completion': completion,
				},
			)

		# Atomically mark as running before releasing lock
		await update_pipeline_state(
			user.id, {'running': True, 'current_agent': 'planning', 'progress': 0, 'jobs_found': 0, 'jobs_applied': 0}
		)

		# Generate session ID for WebSocket events
		session_id = config.session_id or f'pipeline_{user.id}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}'

		# Add pipeline task to background
		background_tasks.add_task(_run_pipeline_task, user.id, session_id, config.model_dump())

		response_payload = {
			'status': 'started',
			'message': 'Pipeline started successfully',
			'session_id': session_id,
			'config': config.model_dump(),
		}
		# Always store idempotency to guard against rapid retries
		await idempotency_store.set(idempotency_lookup, 200, response_payload, ttl_seconds=900)
		return response_payload
	finally:
		await distributed_lock_manager.release(lock_key, lock_token)


@router.post('/stop', response_model=PipelineActionResponse)
async def stop_pipeline(
	user: Annotated[AuthUser, Depends(get_current_user)],
	idempotency_key: Annotated[Optional[str], Header(alias='Idempotency-Key')] = None,
):
	"""
	Stop the running pipeline.
	"""
	if idempotency_key:
		idempotency_lookup = f'pipeline:stop:{user.id}:{idempotency_key}'
		cached = await idempotency_store.get(idempotency_lookup)
		if cached:
			return cached.response

	lock_key = f'pipeline:stop:{user.id}'
	lock_token = await distributed_lock_manager.acquire(lock_key, ttl_seconds=15)
	if not lock_token:
		raise HTTPException(status_code=409, detail='Pipeline stop is already in progress. Please retry.')

	try:
		# Stop the active orchestrator if exists
		if user.id in _active_orchestrators:
			_active_orchestrators[user.id].stop()
			del _active_orchestrators[user.id]

		await update_pipeline_state(user.id, {'running': False, 'current_agent': None})

		response_payload = {
			'status': 'stopped',
			'message': 'Pipeline stopped',
		}
		if idempotency_key:
			await idempotency_store.set(idempotency_lookup, 200, response_payload, ttl_seconds=600)
		return response_payload
	finally:
		await distributed_lock_manager.release(lock_key, lock_token)


@router.post('/pause', response_model=PipelineActionResponse)
async def pause_pipeline(user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Pause the running pipeline.
	"""
	state = await get_pipeline_state(user.id)

	if not state['running']:
		raise HTTPException(status_code=400, detail='Pipeline is not running')

	if user.id in _active_orchestrators:
		_active_orchestrators[user.id].stop()

	await update_pipeline_state(user.id, {'running': False})

	return {
		'status': 'paused',
		'message': 'Pipeline paused',
	}


@router.websocket('/ws/{session_id}')
async def pipeline_websocket(websocket: WebSocket, session_id: str):
	"""
	WebSocket endpoint for real-time pipeline updates.
	Secured via Token in Query Param.
	"""
	# Accept the WebSocket connection FIRST
	await websocket.accept()
	logger.info(f'Pipeline WebSocket connection accepted for session: {session_id}')

	# Extract and verify token
	token = websocket.query_params.get('token')
	enforce_ws_auth = settings.is_production or settings.ws_auth_required
	user_id = None
	if token:
		try:
			from src.core.auth import verify_token

			payload = verify_token(token)
			user_id = payload.get('sub')
			logger.info(f'Pipeline WS authenticated user: {user_id}')
		except Exception as e:
			logger.warning(f'Pipeline WS auth failed for session {session_id}: {e}')
			await websocket.send_json({'type': 'error', 'message': 'Authentication failed'})
			await websocket.close(code=4001, reason='Authentication failed')
			manager.disconnect(session_id)
			return
	elif enforce_ws_auth:
		await websocket.send_json({'type': 'error', 'message': 'Authentication required'})
		await websocket.close(code=4001, reason='Authentication required')
		manager.disconnect(session_id)
		return

	# Register with connection manager
	await manager.connect(websocket, session_id, token, user_id=user_id)

	try:
		while True:
			# Listen for client messages
			data = await websocket.receive_text()
			logger.debug(f'Pipeline WS received from {session_id}: {data[:100]}')

			# Handle ping/pong (both raw text and JSON format)
			try:
				import json

				msg = json.loads(data)
				if msg.get('type') == 'ping':
					await websocket.send_json({'type': 'pong'})
					continue
				if msg.get('type') in ('hitl_response', 'hitl:response'):
					hitl_id = msg.get('hitl_id')
					response = msg.get('response', '')
					if hitl_id:
						manager.resolve_hitl(hitl_id, response)
					continue
				if msg.get('type') == 'chat:message':
					# Broadcast chat message to session
					payload = msg.get('data') or msg
					message = payload.get('message', '')
					sender = payload.get('sender', 'user')
					if message:
						await manager.send_event(
							session_id, AgentEvent(type=EventType.CHAT_MESSAGE, agent=sender, message=message, data=payload)
						)
					continue
			except json.JSONDecodeError:
				pass

			if data == 'ping':
				await websocket.send_text('pong')

	except WebSocketDisconnect:
		logger.info(f'Pipeline WebSocket disconnected: {session_id}')
		manager.disconnect(session_id)
	except Exception as e:
		logger.error(f'Pipeline WebSocket error for {session_id}: {e}')
		manager.disconnect(session_id)


@router.post('/hitl/respond', response_model=HITLResponse)
async def respond_to_hitl(response: dict, user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Respond to a Human-in-the-Loop prompt.
	"""
	hitl_id = response.get('hitl_id')
	answer = response.get('response', '')

	if not hitl_id:
		raise HTTPException(status_code=400, detail='hitl_id is required')

	resolved = manager.resolve_hitl(hitl_id, answer)
	if not resolved:
		raise HTTPException(status_code=404, detail='HITL prompt not found or already resolved')

	return {
		'status': 'resolved',
		'hitl_id': hitl_id,
		'message': 'Response recorded, pipeline continuing',
	}
