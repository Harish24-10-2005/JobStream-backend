"""
Company Research Routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict

from src.agents.company_agent import company_agent

router = APIRouter()

class CompanyResearchRequest(BaseModel):
    company: str
    role: Optional[str] = ""
    job_description: Optional[str] = ""

class CompanyResearchResponse(BaseModel):
    success: bool
    company: str
    company_info: Dict
    culture_analysis: Dict
    red_flags: Dict
    interview_insights: Dict
    error: Optional[str] = None

@router.post("/research", response_model=CompanyResearchResponse)
async def research_company(request: CompanyResearchRequest):
    """
    Research a company deeply.
    """
    try:
        result = await company_agent.research_company(
            company=request.company,
            role=request.role,
            job_description=request.job_description
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================================================================
# NEW: Market-Ready "Insider Dossier" Endpoints
# ==================================================================

@router.post("/generate-dossier")
async def generate_company_dossier(
    request: CompanyResearchRequest,
    user_id: Optional[str] = None # In propd use Depends(auth)
):
    """
    Generate a PDF 'Insider Dossier' for the company.
    Persists the report and returns the ID.
    """
    try:
        # 1. Run Research
        research_data = await company_agent.research_company(
            company=request.company,
            role=request.role,
            job_description=request.job_description
        )
        
        # 2. Persist to DB
        from src.services.company_service import company_service
        # Use dummy ID for testing if no auth yet
        uid = user_id or "00000000-0000-0000-0000-000000000000"
        
        report_id = await company_service.save_report(
            user_id=uid,
            company_name=request.company,
            report_data=research_data
        )
        
        return {
            "success": True,
            "report_id": report_id,
            "message": "Dossier generated successfully. Use GET /reports/{id}/download to retrieve PDF."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/{report_id}/download")
async def download_dossier(report_id: str):
    """
    Download the PDF dossier.
    Generates it on-the-fly from saved JSON data.
    """
    try:
        from src.services.company_service import company_service
        from src.services.pdf_service import pdf_service
        from fastapi.responses import FileResponse
        
        # Fetch data
        # In prod: get user_id from auth
        uid = "00000000-0000-0000-0000-000000000000" 
        report = await company_service.get_report(report_id, uid)
        
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
            
        # Generate PDF
        filename = f"{report['company_name'].replace(' ', '_')}_Insider_Dossier.pdf"
        file_path = pdf_service.generate_company_dossier(report['report_data'], filename)
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/pdf'
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
