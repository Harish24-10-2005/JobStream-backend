"""
Company Research Routes
"""

from typing import Annotated, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from src.agents.company_agent import company_agent
from src.core.auth import AuthUser, get_current_user
from src.core.circuit_breaker import CircuitBreaker
from src.core.distributed_lock import distributed_lock_manager
from src.core.idempotency import idempotency_store

router = APIRouter()
cb_company_persistence = CircuitBreaker('company_report_persistence', failure_threshold=3, retry_count=1, retry_delay=0.25)
cb_company_pdf = CircuitBreaker('company_report_pdf_generation', failure_threshold=3, retry_count=1, retry_delay=0.25)


class CompanyResearchRequest(BaseModel):
	company: str
	role: Optional[str] = ''
	job_description: Optional[str] = ''


class CompanyResearchResponse(BaseModel):
	success: bool
	company: str
	company_info: Dict
	culture_analysis: Dict
	red_flags: Dict
	interview_insights: Dict
	error: Optional[str] = None


@router.post('/research', response_model=CompanyResearchResponse)
async def research_company(request: CompanyResearchRequest, current_user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Research a company deeply.
	"""
	try:
		result = await company_agent.research_company(
			company=request.company, role=request.role, job_description=request.job_description
		)
		return result
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


# ==================================================================
# NEW: Market-Ready "Insider Dossier" Endpoints
# ==================================================================


@router.post('/generate-dossier')
async def generate_company_dossier(
	request: CompanyResearchRequest,
	current_user: Annotated[AuthUser, Depends(get_current_user)],
	idempotency_key: Annotated[Optional[str], Header(alias='Idempotency-Key')] = None,
):
	"""
	Generate a PDF 'Insider Dossier' for the company.
	Persists the report and returns the ID.
	"""
	if idempotency_key:
		idempotency_lookup = (
			f'company:generate-dossier:{current_user.id}:{request.company.strip().lower()}:{idempotency_key}'
		)
		cached = await idempotency_store.get(idempotency_lookup)
		if cached:
			return cached.response

	lock_key = f'company:generate-dossier:{current_user.id}:{request.company.strip().lower()}'
	lock_token = await distributed_lock_manager.acquire(lock_key, ttl_seconds=45)
	if not lock_token:
		raise HTTPException(status_code=409, detail='Dossier generation already in progress for this company.')

	try:
		# 1. Run Research
		research_data = await company_agent.research_company(
			company=request.company, role=request.role, job_description=request.job_description
		)

		# 2. Persist to DB
		from src.services.company_service import company_service

		# Use dummy ID for testing if no auth yet
		uid = current_user.id

		report_id = await cb_company_persistence.call(
			company_service.save_report, user_id=uid, company_name=request.company, report_data=research_data
		)
		if not report_id:
			raise HTTPException(status_code=500, detail='Failed to persist dossier report')

		response_payload = {
			'success': True,
			'report_id': report_id,
			'message': 'Dossier generated successfully. Use GET /reports/{id}/download to retrieve PDF.',
		}
		if idempotency_key:
			await idempotency_store.set(idempotency_lookup, 200, response_payload, ttl_seconds=1800)
		return response_payload
	except HTTPException:
		raise  # Re-raise HTTP exceptions as-is
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
	finally:
		await distributed_lock_manager.release(lock_key, lock_token)


@router.get('/reports/{report_id}/download')
async def download_dossier(report_id: str, current_user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Download the PDF dossier.
	Generates it on-the-fly from saved JSON data.
	"""
	try:
		from fastapi.responses import FileResponse

		from src.services.company_service import company_service
		from src.services.pdf_service import pdf_service

		# Fetch data
		# In prod: get user_id from auth
		uid = current_user.id
		report = await cb_company_persistence.call(company_service.get_report, report_id, uid)

		if not report:
			raise HTTPException(status_code=404, detail='Report not found')

		# Generate PDF
		filename = f'{report["company_name"].replace(" ", "_")}_Insider_Dossier.pdf'
		file_path = cb_company_pdf.call_sync(pdf_service.generate_company_dossier, report['report_data'], filename)

		return FileResponse(path=file_path, filename=filename, media_type='application/pdf')

	except HTTPException:
		raise  # Re-raise HTTP exceptions as-is
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
