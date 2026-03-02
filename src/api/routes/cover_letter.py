"""
Cover Letter API Routes - Generation and Management
"""

import logging
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.agents import get_cover_letter_agent
from src.api.schemas import CoverLetterGenerateResponse
from src.core.auth import AuthUser, get_current_user
from src.models.job import JobAnalysis
from src.services.resume_storage_service import resume_storage_service
from src.services.user_profile_service import user_profile_service as profile_svc

router = APIRouter()
logger = logging.getLogger(__name__)


class CoverLetterRequest(BaseModel):
	role: str
	company: str
	tech_stack: List[str] = []
	tone: str = 'professional'  # professional, enthusiastic, formal, casual
	job_description: Optional[str] = None


@router.post('/generate', response_model=CoverLetterGenerateResponse)
async def generate_cover_letter(request: CoverLetterRequest, current_user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Generate a personalized cover letter.
	"""
	try:
		user_id = current_user.id

		# 1. Fetch Profile
		user_profile = await profile_svc.get_profile(user_id)
		if not user_profile:
			# Fallback if profile doesn't exist yet (edge case)
			raise HTTPException(status_code=404, detail='User profile required. Please complete onboard.')

		# 2. Prepare Job Analysis
		job_analysis = JobAnalysis(
			role=request.role,
			company=request.company,
			tech_stack=request.tech_stack or [],
			matching_skills=[],
			missing_skills=[],
			match_score=0,
		)

		# Auto-approve HITL for HTTP requests
		async def api_hitl_handler(question: str, context: str = "") -> str:
			return "approved"

		# 3. Run Agent (Handles RAG + Persistence)
		agent = get_cover_letter_agent()
		result = await agent.run(
			job_analysis=job_analysis, 
			user_profile=user_profile, 
			tone=request.tone, 
			user_id=user_id,
			hitl_handler=api_hitl_handler
		)

		if not result.success:
			raise HTTPException(status_code=500, detail=result.error)

		data = result.data or {}
		# Normalize response for frontend compatibility
		full_text = data.get('full_text')
		structured = data.get('content')
		content_text = full_text
		if not content_text:
			if isinstance(structured, dict):
				content_text = '\n\n'.join(
					[
						structured.get('greeting', ''),
						structured.get('opening', ''),
						structured.get('body', ''),
						structured.get('closing', ''),
						structured.get('signature', ''),
					]
				).strip()
			else:
				content_text = str(structured) if structured else ''
		return {
			'success': True,
			'content': content_text,
			'full_text': full_text,
			'structured_content': structured,
			'job_title': data.get('job_title'),
			'company_name': data.get('company_name'),
			'tone': data.get('tone'),
		}

	except HTTPException:
		raise  # Re-raise HTTP exceptions as-is (don't wrap 404 as 500)
	except Exception as e:
		logger.error(f'Cover letter generation failed: {e}')
		raise HTTPException(status_code=500, detail=str(e))


from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio

@router.websocket('/ws-generate')
async def ws_generate_cover_letter(websocket: WebSocket, token: str):
	"""
	WebSocket endpoint for generating a cover letter with HITL support.
	"""
	await websocket.accept()
	
	try:
		# Verify token manually since Depends doesn't work the same in WebSockets
		from src.core.auth import verify_token
		payload = verify_token(token)
		if not payload:
			await websocket.send_json({"type": "error", "message": "Invalid token"})
			await websocket.close()
			return
			
		user_id = str(payload.get("sub", ""))
		if not user_id:
			await websocket.send_json({"type": "error", "message": "Invalid token payload"})
			await websocket.close()
			return
		# Wait for the initialization parameters
		data_str = await websocket.receive_text()
		request_data = json.loads(data_str)
		
		if request_data.get("action") != "generate":
			await websocket.send_json({"type": "error", "message": "Expected action: generate"})
			await websocket.close()
			return
			
		role = request_data.get("role", "")
		company = request_data.get("company", "")
		tech_stack = request_data.get("tech_stack", [])
		tone = request_data.get("tone", "professional")
		
		# 1. Fetch Profile
		user_profile = await profile_svc.get_profile(user_id)
		if not user_profile:
			await websocket.send_json({"type": "error", "message": "User profile required. Please complete onboard."})
			await websocket.close()
			return

		# 2. Prepare Job Analysis
		job_analysis = JobAnalysis(
			role=role,
			company=company,
			tech_stack=tech_stack,
			matching_skills=[],
			missing_skills=[],
			match_score=0,
		)

		hitl_event = asyncio.Event()
		hitl_response_queue = asyncio.Queue()

		async def ws_hitl_handler(question: str, context: str = "") -> str:
			# Send HITL request to client
			await websocket.send_json({
				"type": "hitl:request",
				"message": question,
				"context": context
			})
			
			# Signal that we are waiting
			hitl_event.set()
			
			# Wait for response from the client
			response = await hitl_response_queue.get()
			
			# Reset event
			hitl_event.clear()
			return response

		# Start a background task to read from websocket
		async def ws_reader():
			try:
				while True:
					data = await websocket.receive_text()
					msg = json.loads(data)
					if msg.get("action") == "hitl_response" and hitl_event.is_set():
						await hitl_response_queue.put(msg.get("text", ""))
			except WebSocketDisconnect:
				logger.info("Cover letter websocket disconnected")
				if hitl_event.is_set():
					await hitl_response_queue.put("abort")
			except Exception as e:
				logger.error(f"Error reading from cover letter websocket: {e}")

		reader_task = asyncio.create_task(ws_reader())

		# 3. Run Agent
		await websocket.send_json({"type": "status", "message": "Starting cover letter generation..."})
		agent = get_cover_letter_agent()
		
		try:
			result = await agent.run(
				job_analysis=job_analysis, 
				user_profile=user_profile, 
				tone=tone, 
				user_id=user_id,
				hitl_handler=ws_hitl_handler
			)
			
			if not result.success:
				await websocket.send_json({"type": "error", "message": result.error})
			else:
				# Add final cover letter to the response
				data = result.data or {}
				full_text = data.get('full_text')
				structured = data.get('content')
				content_text = full_text
				if not content_text:
					if isinstance(structured, dict):
						content_text = '\n\n'.join(
							[
								structured.get('greeting', ''),
								structured.get('opening', ''),
								structured.get('body', ''),
								structured.get('closing', ''),
								structured.get('signature', ''),
							]
						).strip()
					else:
						content_text = str(structured) if structured else ''
						
				response_data = {
					'success': True,
					'content': content_text,
					'full_text': full_text,
					'structured_content': structured,
					'job_title': data.get('job_title'),
					'company_name': data.get('company_name'),
					'tone': data.get('tone'),
				}
				await websocket.send_json({"type": "complete", "data": response_data})
		finally:
			reader_task.cancel()
			
	except WebSocketDisconnect:
		logger.info("Cover letter client disconnected early.")
	except Exception as e:
		logger.exception(f"Cover letter ws generation failed: {e}")
		try:
			await websocket.send_json({"type": "error", "message": str(e)})
		except:
			pass
	finally:
		try:
			await websocket.close()
		except:
			pass

@router.get('/history', response_model=List[Dict[str, Any]])
async def get_cover_letter_history(current_user: Annotated[AuthUser, Depends(get_current_user)], limit: int = 20):
	"""Get history of generated cover letters."""
	return await resume_storage_service.get_cover_letters(current_user.id, limit)


@router.get('/{letter_id}')
async def get_cover_letter(letter_id: str, current_user: Annotated[AuthUser, Depends(get_current_user)]):
	"""Get specific cover letter details."""
	letter = await resume_storage_service.get_cover_letter(current_user.id, letter_id)
	if not letter:
		raise HTTPException(status_code=404, detail='Cover letter not found')
	return letter
