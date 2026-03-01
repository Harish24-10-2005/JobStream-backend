import io
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.api.schemas import RAGQueryResponse, RAGUploadResponse
from src.core.auth import AuthUser, get_current_user
from src.services.rag_service import rag_service

router = APIRouter()
logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
	query: str
	k: int = 4


@router.post('/upload', response_model=RAGUploadResponse)
async def upload_document(file: Annotated[UploadFile, File()], current_user: Annotated[AuthUser, Depends(get_current_user)]):
	"""Upload a document (PDF/TXT/MD) to the user's RAG context."""
	if not file:
		raise HTTPException(status_code=400, detail='No file uploaded')

	content = ''
	filename = file.filename.lower()

	try:
		# Read file
		file_bytes = await file.read()

		if filename.endswith('.pdf'):
			import pypdf

			pdf = pypdf.PdfReader(io.BytesIO(file_bytes))
			for page in pdf.pages:
				content += page.extract_text() + '\n'

		elif filename.endswith('.txt') or filename.endswith('.md'):
			content = file_bytes.decode('utf-8')
		else:
			raise HTTPException(status_code=400, detail='Unsupported file format. Use PDF, TXT, or MD.')

		if not content.strip():
			raise HTTPException(status_code=400, detail='Could not extract text from file.')

		# Add to RAG
		metadata = {'source': filename}
		await rag_service.add_document(current_user.id, content, metadata)

		return {'status': 'success', 'message': f'Indexed {len(content)} characters from {filename}'}

	except Exception as e:
		logger.error(f'Upload failed: {e}')
		raise HTTPException(status_code=500, detail=str(e))


@router.post('/query', response_model=RAGQueryResponse)
async def query_rag(request: QueryRequest, current_user: Annotated[AuthUser, Depends(get_current_user)]):
	"""Debug endpoint to query the RAG system directly."""
	results = await rag_service.query(current_user.id, request.query, request.k)
	return {'results': results}
