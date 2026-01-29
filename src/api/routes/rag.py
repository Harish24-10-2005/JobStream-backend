
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List
from pydantic import BaseModel
import io
import logging

from src.services.rag_service import rag_service
# Assuming we have auth dependency to get user_id
# If not, we might need to mock or use a header for now, based on existing patterns.
# I'll check if there's an auth dependency. For now, I'll accept user_id as Form param for simplicity/testing,
# or strictly from auth token if available. The LiveApplier uses `user_id` passed in.
# I'll check main.py or other endpoints for auth pattern. 
# For safety, I'll require `user_id` in the form.

router = APIRouter()
logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    user_id: str
    query: str
    k: int = 4

@router.post("/upload")
async def upload_document(
    user_id: str = Form(...),
    file: UploadFile = File(...)
):
    """Upload a document (PDF/TXT/MD) to the user's RAG context."""
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    content = ""
    filename = file.filename.lower()
    
    try:
        # Read file
        file_bytes = await file.read()
        
        if filename.endswith(".pdf"):
            import pypdf
            pdf = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in pdf.pages:
                content += page.extract_text() + "\n"
                
        elif filename.endswith(".txt") or filename.endswith(".md"):
            content = file_bytes.decode("utf-8")
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Use PDF, TXT, or MD.")
        
        if not content.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from file.")
            
        # Add to RAG
        metadata = {"source": filename}
        await rag_service.add_document(user_id, content, metadata)
        
        return {"status": "success", "message": f"Indexed {len(content)} characters from {filename}"}
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query")
async def query_rag(request: QueryRequest):
    """Debug endpoint to query the RAG system directly."""
    results = await rag_service.query(request.user_id, request.query, request.k)
    return {"results": results}
