"""
Agents API Routes
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.schemas import AgentInvokeResponse, AgentListResponse, AgentStatusItem
from src.core.auth import AuthUser, get_current_user

router = APIRouter()


class AgentStatus(BaseModel):
	id: str
	name: str
	status: str  # idle, running, paused, completed, error
	progress: int
	message: str


@router.get('/status', response_model=AgentListResponse)
async def get_all_agents_status(user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Get status of all agents.
	"""
	return {
		'agents': [
			{'id': 'scout', 'name': 'Scout Agent', 'status': 'idle', 'progress': 0, 'message': 'Ready to search'},
			{'id': 'analyst', 'name': 'Analyst Agent', 'status': 'idle', 'progress': 0, 'message': 'Waiting for jobs'},
			{'id': 'applier', 'name': 'Applier Agent', 'status': 'idle', 'progress': 0, 'message': 'Waiting for analysis'},
			{'id': 'resume', 'name': 'Resume Agent', 'status': 'idle', 'progress': 0, 'message': 'Ready'},
			{'id': 'company', 'name': 'Company Agent', 'status': 'idle', 'progress': 0, 'message': 'Ready'},
			{'id': 'interview', 'name': 'Interview Agent', 'status': 'idle', 'progress': 0, 'message': 'Ready'},
		]
	}


@router.get('/status/{agent_id}', response_model=AgentStatusItem)
async def get_agent_status(agent_id: str, user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Get status of a specific agent.
	"""
	agents = {
		'scout': {'id': 'scout', 'name': 'Scout Agent', 'status': 'idle', 'progress': 0, 'message': 'Ready to search'},
		'analyst': {'id': 'analyst', 'name': 'Analyst Agent', 'status': 'idle', 'progress': 0, 'message': 'Waiting for jobs'},
		'applier': {'id': 'applier', 'name': 'Applier Agent', 'status': 'idle', 'progress': 0, 'message': 'Waiting for analysis'},
	}

	if agent_id not in agents:
		raise HTTPException(status_code=404, detail=f'Agent {agent_id} not found')

	return agents[agent_id]


@router.post('/{agent_id}/invoke', response_model=AgentInvokeResponse)
async def invoke_agent(agent_id: str, user: Annotated[AuthUser, Depends(get_current_user)], payload: dict = {}):
	"""
	Invoke a specific agent with a payload.
	"""
	return {
		'agent_id': agent_id,
		'status': 'invoked',
		'message': f'{agent_id} agent has been invoked for user {user.id}',
		'task_id': 'task_12345',
	}
