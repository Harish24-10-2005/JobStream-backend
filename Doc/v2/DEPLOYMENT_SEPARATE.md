# Backend Deployment (uv + Separate Frontend)

## 1. Runtime model
1. Backend API service (`FastAPI/Gunicorn`)
2. Worker service (`Celery`)
3. Redis service (or managed Redis)
4. Frontend deployed separately and connected via `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL`

## 2. Environment
Use `backend/.env.production.example` as baseline.

Required:
- `ENVIRONMENT=production`
- `DEBUG=false`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_JWT_SECRET`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `GROQ_API_KEY`
- `SERPAPI_API_KEY`

RAG critical:
- `GEMINI_API_KEY`
- `GEMINI_EMBEDDING_MODEL`
- `RAG_EMBEDDING_DIM`

## 3. Local prod-like with Docker
```bash
cd backend
cp .env.production.example .env
docker compose -f docker-compose.backend.yml up --build -d
```

Health checks:
```bash
curl http://localhost:8000/api/live
curl http://localhost:8000/api/ready
```

## 4. uv-based non-Docker run
```bash
cd backend
uv sync --locked --no-dev
uv run gunicorn src.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000 --timeout 180
uv run celery -A src.worker.celery_app worker -Q browser --loglevel=info
```

## 5. Separate frontend deployment contract
Frontend must use:
- `NEXT_PUBLIC_API_URL=https://<backend-domain>`
- `NEXT_PUBLIC_WS_URL=wss://<backend-domain>`

Backend must set:
- `CORS_ORIGINS=https://<frontend-domain>`
- `WS_AUTH_REQUIRED=true`
