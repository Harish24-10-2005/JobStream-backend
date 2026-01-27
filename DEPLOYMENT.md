# JobAI Multi-User Production Deployment Guide

This guide covers deploying JobAI for multi-user production hosting.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│  Next.js 16 + React 19 (Vercel/Netlify)                         │
│  - Supabase Auth (Google/GitHub OAuth)                          │
│  - WebSocket connection to backend                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ JWT Token
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                  │
│  FastAPI + Uvicorn (Railway/Render)                             │
│  - JWT verification via Supabase JWT Secret                     │
│  - REST API + WebSocket                                          │
│  - User profile service (Supabase DB)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│    SUPABASE      │ │    REDIS     │ │  CELERY WORKER   │
│  - PostgreSQL    │ │  (Upstash)   │ │  (Railway/Render)│
│  - Auth          │ │  - Sessions  │ │  - Browser Tasks │
│  - Storage       │ │  - Rate Limit│ │  - Async Jobs    │
└──────────────────┘ └──────────────┘ └──────────────────┘
```

## Step 1: Supabase Setup

### 1.1 Create Project
1. Go to [supabase.com](https://supabase.com)
2. Create new project
3. Note down:
   - Project URL (`SUPABASE_URL`)
   - Anon Key (`SUPABASE_ANON_KEY`)
   - Service Role Key (`SUPABASE_SERVICE_KEY`)
   - JWT Secret (`SUPABASE_JWT_SECRET`) - Found in Project Settings > API

### 1.2 Run Database Migration
1. Go to SQL Editor in Supabase Dashboard
2. Paste contents of `backend/database/schema.sql`
3. Click "Run"

This creates:
- `user_profiles` - User profile data
- `user_education` - Education history
- `user_experience` - Work experience
- `user_projects` - Projects
- `user_resumes` - Resume file metadata
- `generated_resumes` - AI-tailored resumes
- `cover_letters` - Generated cover letters
- `job_applications` - Application tracking
- `network_contacts` - NetworkAI referral contacts
- `interview_prep` - Interview preparation data

All tables have Row Level Security (RLS) enabled - users can only access their own data.

### 1.3 Create Storage Buckets
1. Go to Storage in Supabase Dashboard
2. Create buckets:
   - `resumes` (Private) - User uploaded resumes
   - `generated-resumes` (Private) - AI-generated PDFs
   - `cover-letters` (Private) - Generated cover letters

3. Add Storage Policy for each bucket:
```sql
-- Allow users to access their own folder
CREATE POLICY "Users can access own folder"
ON storage.objects
FOR ALL
USING (bucket_id = 'resumes' AND auth.uid()::text = (storage.foldername(name))[1]);
```

### 1.4 Enable Auth Providers
1. Go to Authentication > Providers
2. Enable Google OAuth (get credentials from Google Cloud Console)
3. Enable GitHub OAuth (get credentials from GitHub Developer Settings)

## Step 2: Redis Setup (Upstash)

Upstash provides serverless Redis with free tier.

1. Go to [upstash.com](https://upstash.com)
2. Create new Redis database
3. Copy the `UPSTASH_REDIS_REST_URL` (or Redis URL)
4. Format: `rediss://default:PASSWORD@HOST:PORT`

## Step 3: Backend Deployment

### Option A: Railway (Recommended)

1. Create account at [railway.app](https://railway.app)
2. New Project > Deploy from GitHub
3. Select your repository
4. Configure:
   - Root Directory: `backend`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

5. Add Environment Variables:
```env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_JWT_SECRET=your-jwt-secret

# Redis
REDIS_URL=rediss://default:xxx@xxx.upstash.io:6379
CELERY_BROKER_URL=rediss://default:xxx@xxx.upstash.io:6379
CELERY_RESULT_BACKEND=rediss://default:xxx@xxx.upstash.io:6379

# AI APIs
GROQ_API_KEY=gsk_xxx
SERPAPI_API_KEY=xxx
GEMINI_API_KEY=xxx  # For browser automation

# Security
ENCRYPTION_KEY=your-32-char-key
CORS_ORIGINS=https://your-frontend.vercel.app
```

### Option B: Render

1. Create account at [render.com](https://render.com)
2. New > Web Service
3. Connect GitHub repository
4. Configure:
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

5. Add Environment Variables (same as Railway)

### Option C: Docker (Self-hosted)

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium --with-deps

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t jobai-backend .
docker run -p 8000:8000 --env-file .env jobai-backend
```

## Step 4: Celery Worker Deployment (Optional)

For background browser automation tasks:

### Railway Worker
1. Create new service in same project
2. Configure:
   - Root Directory: `backend`
   - Start Command: `celery -A worker.celery_app worker --loglevel=info`

### Docker Compose
```yaml
version: '3.8'
services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    
  worker:
    build: ./backend
    command: celery -A worker.celery_app worker --loglevel=info
    env_file:
      - .env
    depends_on:
      - redis
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

## Step 5: Frontend Deployment

### Vercel (Recommended)

1. Push frontend to GitHub
2. Import project to Vercel
3. Set environment variables:
```env
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
NEXT_PUBLIC_WS_URL=wss://your-backend.railway.app
```

4. Deploy

## Step 6: Frontend Auth Integration

The frontend already has Supabase auth. Update to pass JWT to backend:

```typescript
// In your API calls
const session = await supabase.auth.getSession();
const token = session.data.session?.access_token;

// REST API
fetch(`${API_URL}/api/user/profile`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

// WebSocket (pass user_id in messages)
ws.send(JSON.stringify({
  type: 'start_apply',
  url: 'https://jobs.example.com/apply',
  user_id: session.data.session?.user.id,
  draft_mode: true
}));
```

## API Endpoints

### Public Endpoints
- `GET /` - Health check
- `GET /api/health` - Detailed health
- `GET /api/ready` - Kubernetes readiness
- `GET /api/live` - Kubernetes liveness

### Authenticated Endpoints (JWT Required)

#### User Profile
- `GET /api/user/profile` - Get user profile
- `POST /api/user/profile` - Create profile (onboarding)
- `PUT /api/user/profile` - Update profile
- `GET /api/user/profile/completion` - Profile completion status

#### Education/Experience
- `POST /api/user/education` - Add education
- `POST /api/user/experience` - Add experience
- `POST /api/user/projects` - Add project

#### Resumes
- `POST /api/user/resume/upload` - Upload resume PDF
- `GET /api/user/resumes` - List all resumes
- `GET /api/user/resume/primary` - Get primary resume
- `DELETE /api/user/resume/{id}` - Delete resume
- `GET /api/user/generated-resumes` - Get AI-generated resumes

#### NetworkAI
- `POST /api/network/find-connections` - Find referral connections

### WebSocket
- `ws://host/ws/{session_id}` - Real-time connection

## Security Checklist

- [ ] All tables have RLS enabled
- [ ] JWT Secret is set and matches Supabase
- [ ] CORS origins limited to your frontend domain
- [ ] Rate limiting enabled in production
- [ ] Service role key only used server-side
- [ ] HTTPS enabled (automatic on Railway/Render/Vercel)
- [ ] Debug mode disabled in production

## Monitoring

### Railway
- Built-in metrics and logs
- Set up alerts for errors

### Custom (Optional)
Add to main.py:
```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

## Scaling

### Horizontal Scaling
- Railway/Render: Increase instance count
- Use Redis for session sharing between instances
- WebSocket connections are sticky (single instance per session)

### Database Scaling
- Supabase Pro for connection pooling
- Read replicas for analytics queries

## Troubleshooting

### "JWT validation failed"
- Check `SUPABASE_JWT_SECRET` matches Supabase Dashboard
- Ensure token hasn't expired
- Verify audience is "authenticated"

### "Profile not found"
- User needs to complete onboarding (`POST /api/user/profile`)
- Check RLS policies in Supabase

### "Storage upload failed"
- Check bucket exists and policies are set
- Verify Service Role Key has permissions

### WebSocket disconnects
- Check CORS configuration
- Ensure WebSocket upgrade headers allowed
- Verify Railway/Render WebSocket support enabled
