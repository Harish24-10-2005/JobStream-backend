# 🚀 Deployment Guide

This guide outlines the steps to deploy JobAI to production environments (AWS, Render, Railway, or DigitalOcean).

## 📋 Prerequisites

*   **Docker Engine** (Installed locally or on VM)
*   **Supabase Project** (For PostgreSQL & Auth)
*   **Groq API Key** (For LLM Inference)
*   **SerpAPI Key** (For Job Search)
*   **Arize Phoenix** (Optional, for observability)

## 🏗️ Environment Variables

Create a `.env` file in production:

```ini
# --- Core ---
ENVIRONMENT=production
DEBUG=false
ALLOWED_ORIGINS=["https://your-domain.com"]

# --- Database (Supabase) ---
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret

# --- AI & Search ---
GROQ_API_KEY=gsk_...
SERPAPI_API_KEY=...
BROWSER_USE_API_KEY=...

# --- Broker (Redis) ---
# If using managed Redis (e.g., Upstash)
REDIS_URL=redis://:password@host:port/0

# --- Ops ---
PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:6006
```

## 🐳 Docker Deployment (Recommended)

The entire stack is containerized.

### 1. Build and Run

```bash
# Build the image
docker build -t jobai-backend:latest .

# Run with environment file
docker run -d \
  --name jobai-api \
  --env-file .env \
  -p 80:8000 \
  jobai-backend:latest
```

### 2. Using Docker Compose (Single Instance)

If deploying to a VM (EC2/Droplet):

```bash
docker-compose up -d --build
```

### 3. Scaling Workers

To process more job applications in parallel, scale the worker container:

```bash
docker-compose up -d --scale worker=5
```

## ☁️ Cloud Platforms

### Render / Railway (Paas)
1.  Connect GitHub Repository.
2.  Set `Dockerfile` as the build source.
3.  Add configured Environment Variables.
4.  Deploy.
5.  **Note:** You will need a separate Redis instance (e.g., Upstash) for the Celery Broker.

## 🩺 Health Checks

*   **API Health:** `GET /api/health` - Returns 200 OK.
*   **Worker Check:** Monitor Celery logs for `Ready to accept tasks`.
