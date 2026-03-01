"""
Interview Prep Routes
"""

import logging
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.agents import get_interview_agent
from src.core.auth import AuthUser, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


class InterviewPrepRequest(BaseModel):
	role: str
	company: str
	tech_stack: List[str]


class InterviewPrepResponse(BaseModel):
	success: bool
	analysis: Dict
	resources: Dict
	behavioral_questions: Dict
	technical_questions: Dict
	error: Optional[str] = None


@router.post('/prep', response_model=InterviewPrepResponse)
async def prepare_interview(request: InterviewPrepRequest, user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Generate interview preparation materials.
	"""
	try:
		interview_agent = get_interview_agent()
		result = await interview_agent.quick_prep(
			role=request.role, company=request.company, tech_stack=request.tech_stack, user_id=user.id
		)
		return result
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


# ==================================================================
# NEW: Real-Time Roleplay WebSocket
# ==================================================================
from src.services.interview_service import interview_service


@router.websocket('/ws/session/{session_id}')
async def interview_websocket(websocket: WebSocket, session_id: str):
	"""
	Real-time interview session.
	Flow:
	1. Client connects (ws://...)
	2. Server validates session
	3. Loop: User sends text -> AI acts as Persona -> Sends text back
	"""
	await websocket.accept()

	# In prod: Verify auth prompt param or header
	# user_id = websocket.query_params.get("token") ...

	try:
		interview_agent = get_interview_agent()
		# Load Session Context
		# (For MVP we trust the session_id exists, or better: fetch it)
		# session = await interview_service.get_session(session_id)

		# Runtime persona settings (query-param override, sensible defaults).
		params = websocket.query_params
		persona_settings = {
			'name': params.get('persona_name', 'Interviewer'),
			'role': params.get('persona_role', 'Senior Engineer'),
			'company': params.get('company', 'Unknown Company'),
			'style': params.get('style', 'Friendly but technical. Digs deep into reasoning.'),
		}

		# Send welcome
		await websocket.send_text(f'Connection established. Session: {session_id}')

		while True:
			# 1. Receive User Input
			data = await websocket.receive_text()

			# 2. Log User Message
			await interview_service.log_message(session_id, 'user', data)

			# 3. Fetch History (Context)
			history = await interview_service.get_session_history(session_id)

			# 4. Generate AI Response
			response_text = await interview_agent.chat_with_persona(
				history=history, current_input=data, persona_settings=persona_settings
			)

			# 5. Log AI Message
			await interview_service.log_message(session_id, 'ai', response_text)

			# 6. Send to Client
			await websocket.send_text(response_text)

	except WebSocketDisconnect:
		logger.info(f'Client disconnected from interview session {session_id}')
	except Exception as e:
		logger.error(f'Interview WebSocket error: {e}')
		await websocket.close()
