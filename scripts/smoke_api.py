"""
Backend API smoke checks with pass/fail matrix.

Usage:
  python scripts/smoke_api.py
  API_BASE_URL=http://localhost:8000 AUTH_BEARER_TOKEN=<jwt> python scripts/smoke_api.py
"""

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import List, Optional

import httpx


@dataclass
class Check:
	name: str
	method: str
	path: str
	auth_required: bool = False
	expected_status: int = 200


@dataclass
class CheckResult:
	name: str
	status: str
	http_status: Optional[int]
	detail: str


CHECKS: List[Check] = [
	Check(name='root', method='GET', path='/'),
	Check(name='health', method='GET', path='/api/health'),
	Check(name='live', method='GET', path='/api/live'),
	Check(name='ready', method='GET', path='/api/ready'),
	Check(name='analytics_system_health', method='GET', path='/api/v1/analytics/system-health', auth_required=True),
	Check(name='pipeline_status', method='GET', path='/api/v1/pipeline/status', auth_required=True),
	Check(name='company_research_contract', method='POST', path='/api/v1/company/research', auth_required=True, expected_status=422),
]


def _fmt_row(columns: List[str]) -> str:
	return ' | '.join(columns)


async def run_check(client: httpx.AsyncClient, check: Check, token: Optional[str]) -> CheckResult:
	if check.auth_required and not token:
		return CheckResult(name=check.name, status='SKIP', http_status=None, detail='missing AUTH_BEARER_TOKEN')

	headers = {}
	if check.auth_required and token:
		headers['Authorization'] = f'Bearer {token}'

	try:
		if check.method == 'GET':
			response = await client.get(check.path, headers=headers)
		elif check.method == 'POST':
			response = await client.post(check.path, headers=headers, json={})
		else:
			return CheckResult(name=check.name, status='FAIL', http_status=None, detail=f'unsupported method {check.method}')
	except Exception as e:
		return CheckResult(name=check.name, status='FAIL', http_status=None, detail=str(e))

	if response.status_code == check.expected_status:
		return CheckResult(name=check.name, status='PASS', http_status=response.status_code, detail='ok')

	# For protected endpoints, 401/403 means endpoint is reachable but auth is not valid.
	if check.auth_required and response.status_code in (401, 403):
		return CheckResult(name=check.name, status='WARN', http_status=response.status_code, detail='auth rejected')

	return CheckResult(
		name=check.name,
		status='FAIL',
		http_status=response.status_code,
		detail=f'expected {check.expected_status}, got {response.status_code}',
	)


async def main():
	base_url = os.getenv('API_BASE_URL', 'http://localhost:8000').rstrip('/')
	token = os.getenv('AUTH_BEARER_TOKEN')
	timeout_seconds = float(os.getenv('SMOKE_TIMEOUT_SECONDS', '8'))

	print(f'Running smoke checks against: {base_url}')
	if token:
		print('Auth token provided: yes')
	else:
		print('Auth token provided: no (auth checks will be skipped)')

	results: List[CheckResult] = []
	async with httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds) as client:
		for check in CHECKS:
			results.append(await run_check(client, check, token))

	print('\n' + _fmt_row(['CHECK', 'STATUS', 'HTTP', 'DETAIL']))
	print(_fmt_row(['-----', '------', '----', '------']))
	for result in results:
		print(_fmt_row([result.name, result.status, str(result.http_status or '-'), result.detail]))

	fails = [r for r in results if r.status == 'FAIL']
	passes = [r for r in results if r.status == 'PASS']
	warns = [r for r in results if r.status == 'WARN']
	skips = [r for r in results if r.status == 'SKIP']

	print(f'\nSummary: PASS={len(passes)} WARN={len(warns)} SKIP={len(skips)} FAIL={len(fails)}')
	sys.exit(1 if fails else 0)


if __name__ == '__main__':
	asyncio.run(main())
