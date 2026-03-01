"""
Credit guardrail middleware.

Applies per-user credits for API usage:
- query credits (request count budget)
- token credits (estimated by endpoint cost profile)
"""

from typing import Callable, Dict, Optional, Tuple

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.auth import verify_token
from src.core.credit_budget import credit_budget_manager

# Endpoint-level estimated credit profile: (query_cost, token_cost_estimate)
ENDPOINT_CREDIT_PROFILE: Dict[str, Tuple[int, int]] = {
	'/api/v1/pipeline/start': (2, 3000),
	'/api/v1/pipeline/stop': (1, 200),
	'/api/v1/company/generate-dossier': (3, 4500),
	'/api/v1/company/research': (2, 3000),
	'/api/v1/interview/prep': (2, 3500),
	'/api/v1/resume/analyze': (1, 1800),
	'/api/v1/resume/tailor': (2, 3000),
	'/api/v1/cover-letter/generate': (2, 3200),
}


class CreditGuardrailMiddleware(BaseHTTPMiddleware):
	def __init__(self, app, enabled: bool = False):
		super().__init__(app)
		self.enabled = enabled

	def _extract_user_key(self, request: Request) -> Optional[str]:
		auth_header = request.headers.get('Authorization', '')
		if auth_header.startswith('Bearer '):
			token = auth_header.split(' ', 1)[1]
			try:
				payload = verify_token(token)
				sub = payload.get('sub')
				if sub:
					return f'user:{sub}'
			except Exception:
				pass
		return None

	def _cost_for_path(self, path: str) -> Tuple[int, int]:
		if path in ENDPOINT_CREDIT_PROFILE:
			return ENDPOINT_CREDIT_PROFILE[path]

		# Fallback heuristic for AI-heavy endpoints
		keywords = ('generate', 'analyze', 'research', 'prep', 'tailor', 'apply')
		if any(part in path for part in keywords):
			return (2, 2200)
		return (1, 200)

	async def dispatch(self, request: Request, call_next: Callable) -> Response:
		if not self.enabled:
			return await call_next(request)

		if request.method in {'GET', 'HEAD', 'OPTIONS'}:
			return await call_next(request)

		if request.url.path in ['/api/health', '/api/ready', '/api/live', '/health', '/']:
			return await call_next(request)

		user_key = self._extract_user_key(request)
		if not user_key:
			# Skip credit checks for anonymous/invalid-token requests.
			# Auth-protected routes will return 401/403 in auth dependencies.
			return await call_next(request)

		query_cost, token_cost = self._cost_for_path(request.url.path)

		if not await credit_budget_manager.can_consume(user_key, query_cost, token_cost):
			balance = await credit_budget_manager.get_balance(user_key)
			raise HTTPException(
				status_code=status.HTTP_402_PAYMENT_REQUIRED,
				detail='Credit budget exhausted',
				headers={
					'X-Credits-Queries-Remaining': str(balance.query_remaining),
					'X-Credits-Tokens-Remaining': str(balance.token_remaining),
				},
			)

		response = await call_next(request)

		if response.status_code < 400:
			balance = await credit_budget_manager.consume(user_key, query_cost, token_cost)
		else:
			balance = await credit_budget_manager.get_balance(user_key)

		response.headers['X-Credits-Queries-Remaining'] = str(balance.query_remaining)
		response.headers['X-Credits-Tokens-Remaining'] = str(balance.token_remaining)
		return response
