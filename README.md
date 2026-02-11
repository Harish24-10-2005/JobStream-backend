# JobAI — Backend Architecture & System Design

> **Production-Grade Agentic Job Application Platform**
>
> A multi-agent AI system that automates the full job search lifecycle — from discovery to application — using LangChain, LangGraph, Playwright, and real-time WebSocket streaming. Built with FastAPI, Supabase, Redis, and Celery for horizontal scalability.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.128.0-009688)
![LangChain](https://img.shields.io/badge/LangChain-1.2.6-green)
![Tests](https://img.shields.io/badge/Tests-52%20Passed-brightgreen)
![Coverage](https://img.shields.io/badge/Coverage-%E2%89%A560%25-yellow)

---

## Table of Contents

1.  [High-Level Architecture](#1-high-level-architecture)
2.  [System Design Decisions](#2-system-design-decisions)
3.  [Application Bootstrap & Lifecycle](#3-application-bootstrap--lifecycle)
4.  [Authentication & Authorization](#4-authentication--authorization)
5.  [LLM Architecture — Multi-Provider Fallback Chain](#5-llm-architecture--multi-provider-fallback-chain)
6.  [Circuit Breaker Pattern](#6-circuit-breaker-pattern)
7.  [Token & Cost Tracking](#7-token--cost-tracking)
8.  [Agent System](#8-agent-system)
9.  [Automator System (Browser Agents)](#9-automator-system-browser-agents)
10. [Pipeline Orchestration](#10-pipeline-orchestration)
11. [WebSocket Architecture](#11-websocket-architecture)
12. [Human-in-the-Loop (HITL)](#12-human-in-the-loop-hitl)
13. [Caching Layer](#13-caching-layer)
14. [Rate Limiting](#14-rate-limiting)
15. [Database Design](#15-database-design)
16. [RAG System (Retrieval-Augmented Generation)](#16-rag-system-retrieval-augmented-generation)
17. [API Design & Versioning](#17-api-design--versioning)
18. [Middleware Stack](#18-middleware-stack)
19. [Error Handling & Exception Hierarchy](#19-error-handling--exception-hierarchy)
20. [Prompt Management System](#20-prompt-management-system)
21. [Task Queue (Celery Workers)](#21-task-queue-celery-workers)
22. [Observability & Structured Logging](#22-observability--structured-logging)
23. [Docker & Deployment](#23-docker--deployment)
24. [CI/CD Pipeline](#24-cicd-pipeline)
25. [Testing Strategy](#25-testing-strategy)
26. [Configuration Management](#26-configuration-management)
27. [Dependency Map](#27-dependency-map)
28. [Data Flow Diagrams](#28-data-flow-diagrams)

---

## 1. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT (Next.js)                                │
│          REST API (/api/v1/*)          WebSocket (/ws/{session_id})          │
└──────────────┬───────────────────────────────────┬───────────────────────────┘
               │                                   │
               ▼                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Application Layer                            │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │Middleware │  │  API Routes  │  │  WebSocket   │  │  Exception         │   │
│  │  Stack    │  │  (13 routers)│  │  Manager     │  │  Handlers          │   │
│  └──────────┘  └──────────────┘  └──────────────┘  └────────────────────┘   │
└──────────────┬───────────────────────────────────┬───────────────────────────┘
               │                                   │
               ▼                                   ▼
┌──────────────────────────┐       ┌─────────────────────────────────────────┐
│    Service Layer          │       │           Agent System                   │
│  ┌──────────────────┐    │       │  ┌─────────┐ ┌─────────┐ ┌──────────┐  │
│  │ DatabaseService   │    │       │  │ Company │ │Interview│ │  Salary  │  │
│  │ UserProfileService│    │       │  │ Agent   │ │ Agent   │ │  Agent   │  │
│  │ RAGService        │    │       │  └─────────┘ └─────────┘ └──────────┘  │
│  │ ResumeService     │    │       │  ┌─────────┐ ┌─────────┐ ┌──────────┐  │
│  │ SalaryService     │    │       │  │ Resume  │ │Cover Ltr│ │ Network  │  │
│  │ NetworkService    │    │       │  │ Agent   │ │(LangGrph│ │  Agent   │  │
│  └──────────────────┘    │       │  └─────────┘ └─────────┘ └──────────┘  │
└──────────┬───────────────┘       └───────────────┬─────────────────────────┘
           │                                       │
           ▼                                       ▼
┌──────────────────────────┐       ┌─────────────────────────────────────────┐
│   Infrastructure Layer    │       │         Automator System                 │
│  ┌────────┐ ┌──────────┐ │       │  ┌────────┐  ┌─────────┐  ┌──────────┐ │
│  │Supabase│ │  Redis   │ │       │  │ Scout  │  │Analyst  │  │ Applier  │ │
│  │(Postgres│ │(Cache +  │ │       │  │(SerpAPI│  │(Scrape +│  │(Playwrght│ │
│  │+pgvector│ │ Queue)   │ │       │  │+Google)│  │  LLM)   │  │+browser) │ │
│  └────────┘ └──────────┘ │       │  └────────┘  └─────────┘  └──────────┘ │
└──────────────────────────┘       └─────────────────────────────────────────┘
```

### Key System Design Properties

| Property | Implementation |
|----------|---------------|
| **Fault Tolerance** | 5-provider LLM fallback chain, circuit breaker, graceful degradation |
| **Resilience** | Exponential backoff with jitter, fail-open rate limiter, in-memory cache fallback |
| **Scalability** | Celery worker pool, Redis pub/sub bridging, stateless REST + stateful WebSocket |
| **Security** | JWT with JWKS rotation, RLS at database level, per-user rate limiting, encrypted credentials |
| **Observability** | Structlog with correlation IDs, LLM cost tracking, Arize Phoenix integration |
| **Real-time** | WebSocket with 40+ event types, session replay buffer, heartbeat keepalive |

---

## 2. System Design Decisions

### Why Multi-Agent over Monolithic LLM?

Each agent specializes in one domain (resume, interview, salary, etc.) with:
- **Domain-specific prompts** tuned for the task
- **Different temperature settings** (e.g., 0.0 for analysis, 0.7 for creative outreach)
- **Independent failure isolation** — one agent crashing doesn't affect others
- **Composable pipeline** — agents can run in sequence or independently

### Why LangGraph for Cover Letters?

Cover letter generation requires **iterative refinement** and **human approval**:
```
plan → research_company → generate_content → format_letter → human_review
                                    ▲                              │
                                    └──── revise (if rejected) ────┘
```
LangGraph's `StateGraph` with conditional edges and `MemorySaver` checkpointing enables this DAG-based workflow with HITL gates — impossible with simple sequential chains.

### Why WebSocket + REST Hybrid?

| Pattern | Use Case |
|---------|----------|
| REST API | CRUD operations, stateless queries, profile management |
| WebSocket | Pipeline progress streaming, browser automation screenshots, HITL prompts/responses |

The pipeline can run for 5-10 minutes processing multiple jobs. REST polling would be wasteful — WebSocket provides sub-second event delivery with bounded replay buffers for reconnection.

### Why Celery + Redis for Browser Tasks?

Browser automation (Playwright) is resource-intensive and long-running (30-120s per application). Running it in the FastAPI process would:
- Block the event loop
- Consume excessive memory (headless Chrome ~200MB per instance)
- Risk timeout issues

Celery workers run in separate processes with `pool=solo` (required for Playwright's async subprocess model), dedicated `browser` queue, and hard time limits (600s).

---

## 3. Application Bootstrap & Lifecycle

### Entry Point: `src/main.py`

```python
app = FastAPI(
    title="JobAI API",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)
```

### Lifespan Events (ASGI Lifecycle)

**Startup:**
1. Log environment, debug mode, rate-limit configuration
2. Initialize OpenTelemetry/Arize Phoenix (if `PHOENIX_COLLECTOR_ENDPOINT` configured)
3. Enforce `WindowsProactorEventLoopPolicy` on Windows (required for Playwright subprocess support)

**Shutdown (Graceful Draining):**
```python
# Step 1: Drain WebSocket connections (close code 1001 = Going Away)
for session_id in list(ws_manager.active_connections.keys()):
    ws = ws_manager.active_connections[session_id]
    await ws.close(code=1001, reason="Server shutting down")

# Step 2: Close Redis cache pool
if hasattr(cache, "redis") and cache.redis:
    await cache.redis.close()

# Step 3: Close rate limiter Redis connection
if hasattr(limiter, "redis") and limiter.redis:
    await limiter.redis.close()
```

### Middleware Registration Order

Middleware executes in **reverse registration order** (last registered = first executed):

```
Request → Security Headers → Request Logging (correlation ID) →
          Request Size Limit → Rate Limit → CORS → Route Handler
```

| Priority | Middleware | Purpose |
|----------|-----------|---------|
| 1st | `SecurityHeadersMiddleware` | `X-Frame-Options`, `CSP`, `X-XSS-Protection` |
| 2nd | `RequestLoggingMiddleware` | UUID correlation ID, structlog context binding, timing |
| 3rd | `RequestSizeLimitMiddleware` | Reject `Content-Length > 10MB` |
| 4th | `RateLimitMiddleware` | IP-based sliding window (100 req/min default) |
| 5th | `CORSMiddleware` | Origin whitelist, credentials, preflight |

### Health Endpoints (Kubernetes-Ready)

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET /` | Root probe | `{"status": "ok"}` |
| `GET /api/health` | Deep health | Version, environment, feature flags |
| `GET /api/ready` | Readiness probe | `{"status": "ready"}` (Kubernetes) |
| `GET /api/live` | Liveness probe | `{"status": "alive"}` (Kubernetes) |

---

## 4. Authentication & Authorization

### Architecture: Supabase JWT with JWKS

```
┌──────────┐        ┌──────────┐        ┌──────────┐
│  Client  │──JWT──▶│ FastAPI  │──JWKS──▶│ Supabase │
│(Next.js) │        │  Auth    │  fetch  │  Auth    │
└──────────┘        │Middleware│◀────────│  Server  │
                    └──────────┘         └──────────┘
```

### `JWTAuth` Class

```python
class JWTAuth:
    def __init__(self):
        self.jwt_secret = settings.supabase_jwt_secret
        self.jwks_cache = None
        self.jwks_cache_time = 0
        self.jwks_ttl = 3600          # 1-hour JWKS cache
        self.clock_skew_leeway = 60   # 60s leeway for clock drift
```

**Token Decoding Strategy:**
1. Read `alg` from JWT header
2. **ES256** (asymmetric): Fetch JWKS from `{supabase_url}/auth/v1/.well-known/jwks.json`, find key by `kid`, verify with RSA public key
3. **HS256** (symmetric): Try base64-decoded secret first, fall back to raw secret string. Audience validation: `"authenticated"`

### FastAPI Dependencies

```python
# Require authentication (raises 401)
user: AuthUser = Depends(get_current_user)

# Optional authentication (returns None if no token)
user: Optional[AuthUser] = Depends(get_optional_user)

# Authentication + per-user rate limiting (60 req/min)
user: AuthUser = Depends(rate_limit_check)
```

### `AuthUser` Model

```python
class AuthUser(BaseModel):
    id: str       # Supabase UUID (from JWT 'sub' claim)
    email: str    # From JWT 'email' claim
    role: str     # Default: "authenticated"
```

### Per-User Rate Limiting

`RateLimitByUser` implements an in-memory sliding window per `user_id`:
- Default: 60 requests per minute per user
- Write endpoints (profile create/update, resume upload) use `rate_limit_check` dependency
- Read endpoints use plain `get_current_user`

---

## 5. LLM Architecture — Multi-Provider Fallback Chain

### Design Pattern: Chain of Responsibility + Strategy

The `UnifiedLLM` class implements a **5-deep fallback chain** across 3 providers, ensuring the system remains operational even when individual LLM providers experience outages or rate limits.

```
   Request
      │
      ▼
┌─────────────┐    fail    ┌─────────────┐    fail    ┌─────────────┐
│ Groq Primary│──────────▶│Groq Fallback│──────────▶│ OpenRouter  │
│ llama-3.1-8b│           │ (API Key 2) │           │  Primary    │
└─────────────┘           └─────────────┘           └──────┬──────┘
                                                           │ fail
                                                           ▼
                                              ┌─────────────┐    fail    ┌──────────┐
                                              │ OpenRouter  │──────────▶│  Gemini  │
                                              │  Fallback   │           │ 2.0-flash│
                                              └─────────────┘           └──────────┘
```

### Provider Configuration

| Provider | Model | Temperature | Max Tokens | Cost ($/1M tokens) |
|----------|-------|-------------|-----------|-------------------|
| Groq Primary | `llama-3.1-8b-instant` | 0.3 | 4096 | $0.05 in / $0.08 out |
| Groq Fallback | `llama-3.1-8b-instant` | 0.3 | 4096 | $0.05 in / $0.08 out |
| OpenRouter Primary | `qwen/qwen3-coder:free` | 0.3 | 4096 | Free tier |
| OpenRouter Fallback | `qwen/qwen3-coder:free` | 0.3 | 4096 | Free tier |
| Gemini | `gemini-2.0-flash-exp` | 0.3 | 4096 | $0.075 in / $0.30 out |

### Invocation Flow

```python
async def invoke(self, messages, agent_name=""):
    for config in self.provider_chain:
        for attempt in range(self.max_retries):  # max_retries=3
            try:
                llm = self._create_llm(config)
                with tracker.track(agent_name, config.provider.value, config.model) as ctx:
                    result = await llm.ainvoke(messages)
                    ctx.record(result)
                return result
            except rate_limit_error:
                await asyncio.sleep(exponential_backoff(attempt))
                continue
            except other_error:
                break  # try next provider
    raise LLMError("All providers exhausted")
```

### Exponential Backoff

```python
def exponential_backoff(attempt, base_delay=1.0, max_delay=60.0) -> float:
    return min(base_delay * (2 ** attempt), max_delay)
    # attempt 0 → 1s, attempt 1 → 2s, attempt 2 → 4s (capped at 60s)
```

### Rate-Limit Detection

String-matching against error messages:
```python
RATE_LIMIT_PATTERNS = [
    "rate_limit", "429", "too many requests",
    "quota exceeded", "tokens per minute", "requests per minute"
]
```

---

## 6. Circuit Breaker Pattern

### State Machine

```
         success
    ┌───────────────┐
    │               ▼
┌───────┐  failure ≥ threshold  ┌──────┐  recovery_timeout  ┌───────────┐
│CLOSED │─────────────────────▶│ OPEN │────────────────────▶│ HALF_OPEN │
└───────┘                      └──────┘                     └─────┬─────┘
    ▲                              ▲                              │
    │              success         │          failure              │
    └──────────────────────────────┴──────────────────────────────┘
```

### Configuration

```python
class CircuitBreaker:
    def __init__(self, name, failure_threshold=5, recovery_timeout=60,
                 expected_exceptions=[Exception]):
```

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `failure_threshold` | 5 | Consecutive failures before opening |
| `recovery_timeout` | 60s | Time before attempting half-open |
| `expected_exceptions` | `[Exception]` | Which exceptions count as failures |

### Usage as Decorator

```python
@circuit_breaker("external_api", failure_threshold=3, recovery_timeout=30)
async def call_external_api():
    ...
```

The decorator attaches `wrapper.breaker` for runtime inspection of circuit state.

---

## 7. Token & Cost Tracking

### Architecture

```
┌──────────────┐    invoke()    ┌──────────────┐     track()     ┌──────────────┐
│   Agent      │──────────────▶│  UnifiedLLM  │───────────────▶│LLMUsageTracker│
│(company,etc) │               │              │                 │  (singleton)  │
└──────────────┘               └──────────────┘                 └───────┬──────┘
                                                                        │
                                                                        ▼
                                                               ┌──────────────┐
                                                               │GET /api/v1/  │
                                                               │admin/llm-usage│
                                                               └──────────────┘
```

### `InvocationContext` — Context Manager

```python
with tracker.track(agent_name, provider, model) as ctx:
    result = await llm.ainvoke(messages)
    ctx.record(result)
# Automatically records: latency_ms, input/output tokens, cost_usd, success/error
```

**Token Extraction Priority:**
1. `result.usage_metadata` (LangChain native) — `input_tokens`, `output_tokens`
2. `result.response_metadata["token_usage"]` — provider-specific
3. `result.response_metadata["usage"]` — fallback

### `TokenUsage` Dataclass

```python
@dataclass
class TokenUsage:
    provider: str          # "groq", "openrouter", "gemini"
    model: str             # "llama-3.1-8b-instant"
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    cost_usd: float        # Estimated from COST_PER_MILLION table
    agent: str             # "company_agent", "resume_agent", etc.
    timestamp: str          # ISO 8601 UTC
    success: bool
    error: Optional[str]
```

### Cost Estimation Table

| Provider | Input ($/1M tokens) | Output ($/1M tokens) |
|----------|--------------------|--------------------|
| `groq` | $0.05 | $0.08 |
| `openrouter` | $0.00 | $0.00 |
| `gemini` | $0.075 | $0.30 |

### Admin API

```
GET /api/v1/admin/llm-usage
```

Response:
```json
{
  "summary": {
    "total_invocations": 142,
    "successful": 138,
    "failed": 4,
    "total_input_tokens": 285000,
    "total_output_tokens": 142000,
    "total_tokens": 427000,
    "estimated_cost_usd": 0.0325,
    "avg_latency_ms": 1250.5
  },
  "per_agent": {
    "company_agent": { "invocations": 30, "total_tokens": 90000, "cost_usd": 0.008 },
    "resume_agent": { "invocations": 25, "total_tokens": 75000, "cost_usd": 0.006 }
  }
}
```

---

## 8. Agent System

### Agent Factory Pattern

```python
# src/agents/__init__.py — Lazy loading to avoid circular imports
def get_resume_agent():
    from src.agents.resume_agent import ResumeAgent
    return ResumeAgent()

def get_cover_letter_agent():
    from src.agents.cover_letter_agent import CoverLetterAgent
    return CoverLetterAgent()
```

### Agent Overview

| Agent | Primary LLM | Temperature | Key Design Pattern |
|-------|-------------|----------|-------------------|
| **CompanyAgent** | Groq llama-3.1-8b | 0.3 | Tool-based (SerpAPI search + LLM synthesis) |
| **InterviewAgent** | Groq llama-3.1-8b | 0.3 | Structured JSON generation + curated resources |
| **SalaryAgent** | Groq llama-3.1-8b | 0.3 | Tool-based (market data + negotiation script gen) |
| **ResumeAgent** | Groq llama-3.1-8b | 0.3 | RAG-enhanced + LaTeX compilation + HITL approval |
| **CoverLetterAgent** | Groq llama-3.3-70b | 0.6 | **LangGraph StateGraph** with HITL conditional edges |
| **NetworkAgent** | Groq llama-3.1-8b | 0.7 | X-Ray search (SerpAPI `site:linkedin.com`) |
| **TrackerAgent** | N/A (data ops) | — | Supabase CRUD + JSON file fallback |

### CompanyAgent — Pre-Interview Research

```python
class CompanyAgent:
    async def run(self, company: str, role: str) -> dict:
        # 1. search_company_info() — SerpAPI Google search
        # 2. analyze_company_culture() — LLM synthesis
        # 3. identify_red_flags() — Glassdoor sentiment analysis
        # 4. get_interview_insights() — Role-specific advice
```

Returns structured JSON: `{ culture, values, red_flags, interview_tips, recent_news }`

### InterviewAgent — AI Interview Coach

```python
class InterviewAgent:
    async def generate_behavioral_questions(self, role, company, tech_stack):
        # STAR framework structured questions
        # Categories: leadership, conflict, failure, collaboration

    async def generate_technical_questions(self, role, tech_stack):
        # DSA + system design + framework-specific questions

    def get_interview_resources(self, tech_stack):
        # Curated links: LeetCode patterns, Glassdoor questions,
        # NeetCode roadmap, system design primers
```

### SalaryAgent — Negotiation Strategy

```python
class SalaryAgent:
    async def research_salary(self, role, location, experience_years):
        # search_market_salary() → percentile ranges (P25/P50/P75/P90)

    async def negotiate_offer(self, role, current_offer, ...):
        # analyze_offer() → market comparison + rating
        # generate_negotiation_script() → email/phone scripts
        # calculate_counter_offer() → leverage-based strategy

    async def negotiate_interactive(self, history, user_input, battle_context):
        # Real-time negotiation battle via WebSocket
```

### ResumeAgent — ATS-Optimized Tailoring

```python
class ResumeAgent:
    async def tailor_resume(self, job_analysis, user_profile, template_type="ats"):
        # 1. extract_job_requirements() — parse JD for keywords
        # 2. RAG query for relevant experience/stories
        # 3. tailor_resume_content() — map experience to requirements
        # 4. generate_latex_resume() — template + PDF compilation
        # 5. calculate_ats_score() — keyword match percentage
        # 6. request_human_approval() — HITL gate (WebSocket or CLI)
```

### CoverLetterAgent — LangGraph DAG

```
┌──────┐    ┌────────────────┐    ┌──────────────────┐    ┌───────────────┐
│ Plan │───▶│Research Company│───▶│Generate Content  │───▶│Format Letter  │
└──────┘    └────────────────┘    └──────────────────┘    └───────┬───────┘
                                          ▲                      │
                                          │                      ▼
                                          │               ┌──────────────┐
                                   revise │               │Human Review  │
                                          │               └──────┬───────┘
                                          │                      │
                                          │            ┌─────────┴─────────┐
                                          │            │                   │
                                          └────────"revise"          "approved"
                                                       │                   │
                                                       ▼                   ▼
                                                   (loop back)      ┌──────────┐
                                                                    │Finalize  │
                                                                    └──────────┘
```

**State Type:**
```python
class CoverLetterState(TypedDict):
    job_analysis: JobAnalysis
    user_profile: UserProfile
    tone: str                    # professional | enthusiastic | formal | casual
    hitl_handler: Any
    plan: str
    company_research: str
    content: dict
    full_text: str
    needs_human_review: bool
    human_approved: bool
    human_feedback: str
    result: dict
    error: Optional[str]
```

**Graph Construction:**
```python
graph = StateGraph(CoverLetterState)
graph.add_node("plan", plan_node)
graph.add_node("research_company", research_node)
graph.add_node("generate_content", generate_node)
graph.add_node("format_letter", format_node)
graph.add_node("human_review", review_node)
graph.add_node("finalize", finalize_node)

graph.add_edge("plan", "research_company")
graph.add_edge("research_company", "generate_content")
graph.add_edge("generate_content", "format_letter")
graph.add_edge("format_letter", "human_review")
graph.add_conditional_edges("human_review", should_continue,
    {"approved": "finalize", "revise": "generate_content", "end": END})
graph.set_entry_point("plan")
```

### NetworkAgent — LinkedIn X-Ray Search

```python
class NetworkAgent:
    async def find_connections(self, company, user_profile, ...):
        # 3 parallel search categories:
        # 1. Alumni: "site:linkedin.com/in/ {university} {company}"
        # 2. Location: "site:linkedin.com/in/ {city} {company}"
        # 3. Past employers: "site:linkedin.com/in/ {prev_company} {company}"
        # Per match: LLM generates personalized outreach (300 chars max)
```

**Why X-Ray Search?** Direct LinkedIn scraping violates ToS and risks account bans. Google X-Ray search (`site:linkedin.com/in/`) queries Google's public index — **zero ban risk**.

---

## 9. Automator System (Browser Agents)

Automators are distinct from agents — they perform **browser automation and web scraping** rather than LLM content generation.

### ScoutAgent — Job Discovery

```python
class ScoutAgent(BaseAgent):
    async def run(self, query, location):
        # SerpAPI with engine=google
        # Targets ATS domains: greenhouse.io, lever.co, ashbyhq.com
        # Freshness params: tbs (day/week/month)
        # Self-correction: if 0 results, uses LLM to broaden query
        #   (llama-3.3-70b-versatile, temp=0.2) → retry up to 2 attempts
```

### AnalystAgent — Job Matching

```python
class AnalystAgent(BaseAgent):
    async def analyze_job(self, url, resume_text=None):
        # 1. Fetch page via requests + BeautifulSoup (cleans to 20K chars)
        # 2. LLM extracts structured data (llama-3.3-70b, temp=0.0)
        # 3. Validates against JobAnalysis Pydantic model
        # Returns: role, company, match_score (0-100), tech_stack,
        #          matching_skills, missing_skills, gap_analysis_advice
```

### ApplierAgent — Browser-Based Application

```python
class ApplierAgent:
    # Uses browser-use library with Playwright Chrome
    # Primary LLM: Gemini 2.0 Flash (vision-capable for form understanding)
    # Fallback: OpenRouter via ChatOpenAI
    # Features:
    #   - Vision-enabled for complex form layouts
    #   - Controller with ask_human action for HITL
    #   - Draft mode: pauses before submission for human review
    #   - User profile injected as YAML for form filling
    #   - RAG tool for context retrieval during filling
```

---

## 10. Pipeline Orchestration

### `StreamingPipelineOrchestrator`

The orchestrator chains all agents into an end-to-end pipeline with real-time event streaming:

```
┌─────────────┐
│   Profile    │ Load from Supabase or YAML fallback
│   Loading    │
└──────┬──────┘
       ▼
┌─────────────┐     ┌════════════════════════════════════════════════════┐
│    Scout     │────▶│              Per Job URL Loop                     │
│  Discovery   │     │                                                   │
└─────────────┘     │  ┌──────────┐  score < min?  ┌────────────────┐  │
                    │  │ Analyst  │────skip───────▶│  Next Job URL  │  │
                    │  │ Analysis │                 └────────────────┘  │
                    │  └────┬─────┘                                     │
                    │       │ score ≥ min                               │
                    │       ▼                                           │
                    │  ┌──────────┐    ┌──────────┐    ┌────────────┐  │
                    │  │ Company  │───▶│  Resume  │───▶│Cover Letter│  │
                    │  │ Research │    │ Tailoring│    │ (LangGraph)│  │
                    │  └──────────┘    └──────────┘    └─────┬──────┘  │
                    │                                        │         │
                    │                                        ▼         │
                    │                                 ┌────────────┐   │
                    │                                 │  Applier   │   │
                    │                                 │ (if auto)  │   │
                    │                                 └────────────┘   │
                    └═══════════════════════════════════════════════════┘
```

### Event Emission

Each stage emits real-time `AgentEvent`s via WebSocket:

```
PIPELINE_START → SCOUT_START → SCOUT_SEARCHING → SCOUT_FOUND(n) → SCOUT_COMPLETE
  → ANALYST_START → ANALYST_FETCHING → ANALYST_ANALYZING → ANALYST_RESULT
  → COMPANY_START → COMPANY_RESEARCHING → COMPANY_RESULT
  → RESUME_START → RESUME_TAILORING → RESUME_GENERATED → RESUME_COMPLETE
  → COVER_LETTER_START → COVER_LETTER_GENERATING → COVER_LETTER_COMPLETE
  → APPLIER_START → APPLIER_NAVIGATE → APPLIER_CLICK → APPLIER_TYPE → APPLIER_COMPLETE
→ PIPELINE_COMPLETE
```

### Stoppable

```python
orchestrator.stop()  # Sets internal flag, checked between stages
```

---

## 11. WebSocket Architecture

### `ConnectionManager` — Singleton

```python
class ConnectionManager:
    MAX_EVENT_HISTORY = 200

    active_connections: Dict[str, WebSocket]      # session_id → WebSocket
    session_user_map: Dict[str, str]              # session_id → user_id
    event_history: Dict[str, deque[AgentEvent]]   # Bounded replay buffer
    hitl_callbacks: Dict[str, asyncio.Future]     # Pending HITL futures
```

### Connection Lifecycle

```
Client WS Connect → accept() → JWT verify (optional) →
  register in active_connections →
  send CONNECTED event →
  replay last 50 events →
  enter receive loop (ping/pong, HITL responses, chat messages)
```

**Reconnection**: If a client reconnects with the same `session_id`, the old connection is closed with code `4000` and replaced. Event history is preserved for replay.

### Event Types (40+)

```python
class EventType(str, Enum):
    # Connection
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"

    # Pipeline control
    PIPELINE_START = "pipeline:start"
    PIPELINE_COMPLETE = "pipeline:complete"
    PIPELINE_ERROR = "pipeline:error"

    # Agent-specific events (Scout, Analyst, Company, Resume, Cover Letter)
    SCOUT_START = "scout:start"
    SCOUT_FOUND = "scout:found"
    # ... (40+ total)

    # Browser automation
    APPLIER_NAVIGATE = "applier:navigate"
    APPLIER_CLICK = "applier:click"
    APPLIER_SCREENSHOT = "applier:screenshot"
    BROWSER_SCREENSHOT = "browser:screenshot"

    # HITL
    HITL_REQUEST = "hitl:request"
    HITL_RESPONSE = "hitl:response"

    # Task queue
    TASK_QUEUED = "task:queued"
    TASK_PROGRESS = "task:progress"
    TASK_COMPLETE = "task:complete"
```

### `AgentEvent` Dataclass

```python
@dataclass
class AgentEvent:
    type: EventType
    agent: str             # "scout", "analyst", "applier", etc.
    message: str           # Human-readable description
    data: Optional[Dict]   # Structured payload
    timestamp: str         # ISO 8601 UTC with 'Z' suffix
```

### Heartbeat

Server sends `{"type": "ping"}` every 30 seconds to keep the connection alive through proxies and load balancers.

---

## 12. Human-in-the-Loop (HITL)

### Design Pattern: Future-Based Async HITL

```
┌──────────┐  HITL_REQUEST  ┌──────────┐  (renders UI)  ┌──────────┐
│  Agent   │───────────────▶│WebSocket │─────────────────▶│  Client  │
│(pipeline)│                │ Manager  │                  │(Next.js) │
└──────────┘                └────┬─────┘                  └────┬─────┘
     │                          │                              │
     │  await future            │  asyncio.Future              │
     │◀─────────────────────────│                              │
     │                          │  HITL_RESPONSE               │
     │                          │◀─────────────────────────────│
     │  resolve future          │  future.set_result(answer)   │
     │◀─────────────────────────│                              │
     ▼                          │                              │
  (continue pipeline)           │                              │
```

### Implementation

```python
# Server side (ConnectionManager)
async def request_hitl(self, session_id, question, context={}) -> str:
    hitl_id = str(uuid.uuid4())
    future = asyncio.get_event_loop().create_future()
    self.hitl_callbacks[hitl_id] = future

    await self.send_event(session_id, AgentEvent(
        type=EventType.HITL_REQUEST,
        agent="system",
        message=question,
        data={"hitl_id": hitl_id, "context": context}
    ))

    return await asyncio.wait_for(future, timeout=300)  # 5-min timeout

def resolve_hitl(self, hitl_id, response):
    future = self.hitl_callbacks.pop(hitl_id, None)
    if future and not future.done():
        future.set_result(response)
        return True
    return False
```

### HITL Use Cases

| Agent | HITL Point | Question |
|-------|-----------|----------|
| ResumeAgent | After ATS score calculation | "Resume scored {score}%. Approve or revise?" |
| CoverLetterAgent | After letter formatting | "Review this cover letter. Approve, revise, or end?" |
| ApplierAgent | Draft mode before submit | "Application filled. Click Submit or Edit?" |

### Celery Worker HITL Bridging

For browser tasks running in Celery workers (separate process), HITL uses Redis pub/sub:

```
Celery Worker → Redis publish(jobai:events:{session_id}) →
  WebSocket Manager subscribes → sends to client →
  Client responds → Redis publish(jobai:hitl:{hitl_id}) →
  Celery Worker subscribes to response channel → continues
```

---

## 13. Caching Layer

### `RedisCache` — Dual-Mode

```python
class RedisCache:
    def __init__(self):
        if settings.redis_url:
            self.redis = redis.asyncio.from_url(settings.redis_url)
        else:
            self.redis = None
            self._memory = {}  # In-memory fallback
```

### Methods

| Method | Purpose | Serialization |
|--------|---------|---------------|
| `get(key)` | Retrieve raw string | N/A |
| `set(key, value, ttl=3600)` | Store raw string | N/A |
| `get_model(key, model_cls)` | Retrieve Pydantic model | `model_validate_json()` |
| `set_model(key, model, ttl)` | Store Pydantic model | `model_dump_json()` |
| `delete(key)` | Remove entry | N/A |

### Design Decision: Graceful Degradation

If Redis is unavailable, the cache falls back to an in-memory `dict`. This means:
- **Development**: Works without Docker Redis
- **Production failure**: Cache misses increase latency but don't crash the system
- **Trade-off**: In-memory cache isn't shared across workers (acceptable for development)

---

## 14. Rate Limiting

### Strategy Pattern: Two Implementations

```python
class BaseRateLimiter(ABC):
    async def is_allowed(self, key, limit, window) -> Tuple[bool, int]: ...

class MemoryRateLimiter(BaseRateLimiter):
    # Sliding window with in-memory timestamp lists
    # Good for: single-worker development

class RedisRateLimiter(BaseRateLimiter):
    # Fixed window using Redis INCR + EXPIRE (atomic pipeline)
    # Key format: rate_limit:{client_ip}:{window_number}
    # Fails open if Redis is down (allows request)
```

### Factory

```python
def get_rate_limiter() -> BaseRateLimiter:
    if settings.redis_url:
        return RedisRateLimiter(settings.redis_url)
    return MemoryRateLimiter()
```

### Two Layers

| Layer | Scope | Default | Implementation |
|-------|-------|---------|----------------|
| **Global (IP-based)** | All requests | 100 req/min | `RateLimitMiddleware` using `limiter` |
| **Per-User** | Write endpoints | 60 req/min | `RateLimitByUser` in auth dependency |

### Response Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
Retry-After: 60  (only on 429)
```

---

## 15. Database Design

### Supabase Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Supabase                           │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │PostgreSQL│  │  Storage  │  │   Auth (GoTrue)   │  │
│  │+ pgvector│  │ (Resumes) │  │  JWT + JWKS       │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
└──────────────────────────────────────────────────────┘
```

### Schema (10 Tables with Row-Level Security)

```sql
-- All tables have RLS enabled with per-user policies:
-- CREATE POLICY "Users can only see own data"
-- ON table_name FOR ALL
-- USING (auth.uid() = user_id);

┌─────────────────────┐       ┌───────────────────────┐
│   user_profiles     │       │   user_education      │
│─────────────────────│       │───────────────────────│
│ user_id (PK, FK)    │──────▶│ user_id (FK)          │
│ first_name          │       │ degree, major          │
│ last_name           │       │ university, cgpa       │
│ full_name (GENERATED│       │ start_date, end_date   │
│ email, phone        │       └───────────────────────┘
│ skills (JSONB)      │
│ behavioral_questions│       ┌───────────────────────┐
│   (JSONB)           │       │   user_experience     │
└─────────────────────┘       │───────────────────────│
         │                    │ user_id (FK)          │
         │                    │ title, company         │
         ▼                    │ start_date, end_date   │
┌─────────────────────┐       │ description            │
│   user_resumes      │       └───────────────────────┘
│─────────────────────│
│ user_id (FK)        │       ┌───────────────────────┐
│ file_path, file_url │       │   user_projects       │
│ is_primary          │       │───────────────────────│
│ parsed_content      │       │ user_id (FK)          │
│   (JSONB)           │       │ name, tech_stack[]     │
└────────┬────────────┘       │ description            │
         │                    └───────────────────────┘
         ▼
┌─────────────────────┐       ┌───────────────────────┐
│  generated_resumes  │       │    cover_letters      │
│─────────────────────│       │───────────────────────│
│ base_resume_id (FK) │       │ resume_id (FK)        │
│ job_title, company  │       │ tone                  │
│ original_content    │       │ content (JSONB)       │
│ tailored_content    │       │ latex_source          │
│   (both JSONB)      │       └───────────────────────┘
│ latex_source        │
│ ats_score           │       ┌───────────────────────┐
│ match_score         │       │  network_contacts     │
└─────────────────────┘       │───────────────────────│
                              │ user_id (FK)          │
┌─────────────────────┐       │ target_company        │
│  job_applications   │       │ connection_type       │
│─────────────────────│       │ outreach_draft        │
│ user_id (FK)        │       │ outreach_sent         │
│ status (ENUM):      │       │ response_received     │
│   discovered →      │       └───────────────────────┘
│   applied →         │
│   interviewing →    │       ┌───────────────────────┐
│   offer → rejected  │       │   interview_prep      │
│ draft_data (JSONB)  │       │───────────────────────│
│ resume_id (FK)      │       │ application_id (FK)   │
│ cover_letter_id(FK) │       │ interview_type        │
└─────────────────────┘       │ questions (JSONB)     │
                              │ answers (JSONB)       │
                              │ feedback (JSONB)      │
                              └───────────────────────┘
```

### Key Design Decisions

- **JSONB for flexible data**: Skills, behavioral questions, parsed resume content — schema-less within structured tables
- **Row-Level Security**: Every table policy checks `auth.uid() = user_id` — data isolation at DB level, not just application level
- **Generated columns**: `full_name` computed from `first_name || ' ' || last_name`
- **`updated_at` triggers**: Automatic timestamp updates on row modification
- **Indexes**: All `user_id` columns + `job_applications.status` for query performance

### Multi-Tenant Data Service

```python
class DatabaseService:
    def get_jobs_with_analyses(self, limit, offset, min_score, source, user_id):
        # All queries scoped to user_id
        query = supabase.table("discovered_jobs").select("*").eq("user_id", user_id)
```

---

## 16. RAG System (Retrieval-Augmented Generation)

### Architecture

```
┌──────────────┐    chunk     ┌──────────────┐    embed     ┌──────────────┐
│  Document    │─────────────▶│   Text       │─────────────▶│   Supabase   │
│  Upload      │  (1000 char  │  Splitter    │  (Google     │  pgvector    │
│  (PDF/TXT)   │   chunks,    │              │  text-004)   │  "documents" │
└──────────────┘   200 overlap)└──────────────┘              └──────┬───────┘
                                                                    │
┌──────────────┐    top-k     ┌──────────────┐  match_documents()   │
│   Agent      │◀─────────────│   RAG        │◀─────────────────────┘
│(Resume/CL)   │  (k=4,       │  Service     │  (threshold=0.5)
└──────────────┘  threshold    └──────────────┘
                  =0.5)
```

### `RAGService`

```python
class RAGService:
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    async def add_document(self, user_id, content, metadata):
        # Split → embed → bulk insert with user_id scoping

    async def sync_user_profile(self, user_id, profile_text):
        # Delete old profile docs → re-add (metadata.type='profile')

    async def query(self, user_id, query_text, k=4):
        # RPC match_documents with filter_user_id, match_threshold=0.5
```

### How Agents Use RAG

| Agent | RAG Query | Purpose |
|-------|-----------|---------|
| ResumeAgent | "Experience relevant to {role}" | Find matching stories for resume bullets |
| CoverLetterAgent | "Achievements related to {company}" | Personalize with real accomplishments |
| ApplierAgent | `retrieve_user_context` tool | Fill application forms with real data |

---

## 17. API Design & Versioning

### Versioning Strategy

```
/api/v1/jobs/search     ← Canonical (versioned)
/api/jobs/search        ← Legacy (backward-compatible, same handler)
```

### Router Aggregation (`src/api/v1.py`)

```python
v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])
v1_router.include_router(agents_router, prefix="/agents", tags=["Agents"])
v1_router.include_router(pipeline_router, prefix="/pipeline", tags=["Pipeline"])
# ... 13 domain routers total
```

### Response Schemas (`src/api/schemas.py`)

All endpoints use `response_model` for automatic OpenAPI documentation and response validation:

```python
@router.post("/search", response_model=JobSearchResponse)
async def search_jobs(request: JobSearchRequest, user: AuthUser = Depends(get_current_user)):
    ...
```

Key response models:

| Schema | Fields | Extra |
|--------|--------|-------|
| `JobSearchResponse` | `status`, `query`, `location`, `jobs[]`, `total` | Strict |
| `JobAnalyzeResponse` | `job_id`, `status`, `cached`, `match_score`, `tech_stack` | `extra="allow"` |
| `PipelineStartResponse` | `status`, `message`, `session_id`, `config` | Strict |
| `CoverLetterGenerateResponse` | `success`, `content`, `full_text`, `structured_content`, `tone` | Strict |
| `LLMUsageResponse` | `summary`, `per_agent` | `extra="allow"` |
| `ProfileCompletionResponse` | `has_profile`, `has_education`, `completion_percent` | Strict |

### API Endpoint Summary

| Domain | Endpoints | Auth | Description |
|--------|-----------|------|-------------|
| `/api/v1/jobs` | `POST /search`, `GET /results`, `GET /{id}`, `POST /analyze/{id}`, `POST /apply/{id}` | JWT | Job discovery, analysis, application |
| `/api/v1/pipeline` | `POST /start`, `POST /stop`, `POST /pause`, `GET /status`, `POST /hitl/respond`, `WS /ws/{session}` | JWT | Full pipeline orchestration |
| `/api/v1/agents` | `GET /status`, `GET /status/{id}`, `POST /{id}/invoke` | JWT | Agent status & invocation |
| `/api/v1/company` | `POST /research` | JWT | Company research |
| `/api/v1/interview` | `POST /prep`, `WS /ws/{session}` | JWT | Interview preparation |
| `/api/v1/salary` | `POST /research`, `POST /negotiate`, `WS /ws/battle/{id}` | JWT | Salary research & negotiation |
| `/api/v1/resume` | `POST /analyze`, `POST /tailor`, `GET /history`, `GET /templates` | JWT | Resume ATS analysis & tailoring |
| `/api/v1/cover-letter` | `POST /generate`, `GET /history`, `GET /{id}` | JWT | Cover letter generation |
| `/api/v1/tracker` | `GET /`, `POST /`, `PATCH /{company}`, `GET /stats` | JWT | Application tracking |
| `/api/v1/network` | `POST /find-connections`, `GET /health` | JWT | LinkedIn X-Ray networking |
| `/api/v1/rag` | `POST /upload`, `POST /query` | JWT | Document ingestion & search |
| `/api/v1/user` | `GET/POST/PUT /profile`, `POST /education`, `POST /experience`, `POST /resume/upload`, etc. | JWT | Full profile CRUD |

---

## 18. Middleware Stack

### Request Flow Through Middleware

```
Incoming Request
    │
    ▼
┌─────────────────────────────┐
│  SecurityHeadersMiddleware   │ Adds X-Frame-Options, CSP, etc.
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│  RequestLoggingMiddleware    │ Generate/propagate X-Request-ID (UUID)
│                             │ Bind structlog context vars
│                             │ Measure processing time
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ RequestSizeLimitMiddleware   │ Reject if Content-Length > 10MB (413)
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│    RateLimitMiddleware       │ IP-based sliding window (100/min)
│                             │ Skips /health, /health/ready, /health/live
│                             │ Adds X-RateLimit-Limit, X-RateLimit-Remaining
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│      CORSMiddleware          │ Origin whitelist, credentials, preflight
└──────────────┬──────────────┘
               ▼
         Route Handler
```

### Correlation ID Propagation

```python
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Generate or propagate correlation ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Bind for entire request lifecycle
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
        )

        response = await call_next(request)

        # Return correlation ID in response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        return response
```

---

## 19. Error Handling & Exception Hierarchy

### Custom Exception Tree

```
JobAIException (base, HTTP 500)
│
├── ValidationError (400)        — Invalid input data
├── NotFoundError (404)          — Resource not found
├── DatabaseError (500)          — Database operation failure
├── AgentError (500)             — Agent execution failure
├── LLMError (429 or 502)       — LLM provider errors
├── AuthenticationError (401)    — Invalid/missing credentials
├── AuthorizationError (403)     — Insufficient permissions
├── RateLimitError (429)         — Rate limit exceeded
└── ExternalServiceError (502)   — Third-party service failure
```

### Serialization

```python
class JobAIException(Exception):
    def __init__(self, message, code="INTERNAL_ERROR", status_code=500, details=None):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details

    def to_dict(self):
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
```

### Global Exception Handlers

```python
# FastAPI HTTP exceptions → JSON with CORS headers
@app.exception_handler(FastAPIHTTPException)
async def http_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "code": f"HTTP_{exc.status_code}", "message": str(exc.detail)},
        headers={"Access-Control-Allow-Origin": "*"},
    )

# Custom exceptions → to_dict()
@app.exception_handler(JobAIException)
async def jobai_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

# Unhandled exceptions → hide details in production
@app.exception_handler(Exception)
async def generic_handler(request, exc):
    detail = str(exc) if settings.debug else "Internal server error"
    return JSONResponse(status_code=500, content={"error": True, "code": "INTERNAL_ERROR", "message": detail})
```

---

## 20. Prompt Management System

### Architecture

```
src/prompts/
├── loader.py              # Template engine
├── applier_agent.py       # Legacy inline prompts
└── templates/
    ├── company.yaml        # 4 prompts (research, culture, red_flags, interview_insights)
    ├── cover_letter.yaml   # Cover letter generation prompts
    ├── interview.yaml      # 4 prompts (behavioral, technical, mock, coach)
    ├── network.yaml        # 3 prompts (outreach, referral, find_leads)
    ├── resume.yaml         # 3 prompts (tailor, extract_requirements, ats_optimize)
    └── salary.yaml         # 3 prompts (research, negotiation_strategy, battle_persona)
```

### YAML Template Format

```yaml
version: "1.0"
domain: company
description: Prompts for company research and analysis.

prompts:
  research:
    description: "Deep company research for interview prep"
    variables: [company, role, search_results]
    template: |
      Analyze {company} for a {role} candidate.
      Market data: {search_results}
      Return JSON: {{ "culture": "...", "values": [...] }}
```

### Loader API

```python
from src.prompts.loader import prompt, list_prompts, get_prompt_metadata, reload

# Render a prompt
text = prompt("company.research", company="Google", role="SDE", search_results="...")

# List all prompts
keys = list_prompts()  # ["company.research", "company.culture", ...]
keys = list_prompts(domain="interview")  # ["interview.behavioral", ...]

# Get metadata
meta = get_prompt_metadata("salary.research")
# → {"domain": "salary", "name": "research", "version": "1.0",
#    "description": "...", "variables": ["role", "location", ...]}

# Hot-reload in development
reload()
```

**Design Decision**: Simple `str.format()` interpolation (no eval, no Jinja2) — safe against injection, zero dependencies.

---

## 21. Task Queue (Celery Workers)

### Architecture

```
┌──────────┐    task.delay()    ┌──────────┐    subscribe    ┌──────────┐
│  FastAPI  │──────────────────▶│  Redis   │◀───────────────│  Celery  │
│  (Web)    │                   │ (Broker) │                 │ (Worker) │
└──────────┘                    └──────────┘                 └──────────┘
     ▲                                                            │
     │              Redis Pub/Sub                                 │
     │◀───────────── jobai:events:{session_id} ───────────────────┘
     │
     ▼
┌──────────┐
│WebSocket │ → Client
│  Manager │
└──────────┘
```

### Celery Configuration

```python
celery_app = Celery("jobai")
celery_app.conf.update(
    task_serializer="json",
    task_acks_late=True,              # Ack after completion (at-least-once)
    task_reject_on_worker_lost=True,  # Re-queue if worker crashes
    task_time_limit=600,              # 10-minute hard timeout
    task_soft_time_limit=540,         # 9-minute soft timeout (SoftTimeLimitExceeded)
    worker_prefetch_multiplier=1,     # Fair scheduling
    worker_concurrency=2,             # 2 browser instances max
    result_expires=3600,              # Results retained for 1 hour
    task_default_retry_delay=30,      # 30s between retries
    task_max_retries=3,
)
```

### Task Routing

```python
task_routes = {"applier_task.*": {"queue": "browser"}}
```

Run command:
```bash
celery -A worker.celery_app worker -Q browser --loglevel=info --pool=solo
```

**Why `--pool=solo`?** Playwright requires async subprocess management, which doesn't work with Celery's default prefork pool. Solo pool runs tasks in the main process, enabling proper async/await execution.

### Applier Task — Redis Event Bridging

```python
@shared_task(bind=True, max_retries=2, soft_time_limit=540, time_limit=600)
def apply_to_job(self, job_url, session_id, draft_mode, redis_url, user_id):
    # 1. Create RedisEventPublisher (bridges events to WebSocket via Redis pub/sub)
    # 2. Create LiveApplierServiceWithDraft (overrides emit() → Redis publish)
    # 3. Run browser automation with Playwright
    # 4. HITL via Redis: publish question → subscribe to response channel
```

---

## 22. Observability & Structured Logging

### Structlog Configuration

```python
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,  # Correlation ID propagation
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),  # or JSONRenderer for production
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
```

### Log Output Example

```
2026-02-09T12:34:56.789Z [info] request_processed
    request_id=a1b2c3d4-e5f6-7890  method=POST  path=/api/v1/jobs/search
    client_ip=192.168.1.1  status_code=200  process_time_ms=142.35
```

### Arize Phoenix Integration (Optional)

When `PHOENIX_COLLECTOR_ENDPOINT` is configured:
- OpenInference instrumentation for LangChain
- Traces LLM calls, chain executions, token usage
- Provides a UI dashboard for LLM observability

### LLM Usage Tracking

See [Section 7](#7-token--cost-tracking) — every LLM invocation is tracked with latency, tokens, cost, and agent attribution.

---

## 23. Docker & Deployment

### Multi-Stage Dockerfile

```dockerfile
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime with Chrome
FROM python:3.11-slim AS runtime
# Install Chrome + Playwright dependencies
RUN apt-get install -y google-chrome-stable
RUN playwright install chromium --with-deps

# Non-root user
RUN useradd --create-home jobai
USER jobai

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

CMD ["gunicorn", "src.main:app",
     "--workers", "${WORKERS:-2}",
     "--worker-class", "uvicorn.workers.UvicornWorker",
     "--bind", "0.0.0.0:${PORT:-8000}",
     "--timeout", "120",
     "--graceful-timeout", "30"]
```

### docker-compose.yml

```yaml
services:
  backend:
    build: .
    env_file: .env
    ports:
      - "${PORT:-8000}:${PORT:-8000}"
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    profiles:
      - with-redis  # Optional: only starts when explicitly requested
```

### Security Hardening

- Non-root user (`jobai`)
- Multi-stage build (no build tools in runtime)
- Health checks with start period
- Graceful shutdown timeout (30s)
- `--no-cache-dir` pip install

---

## 24. CI/CD Pipeline

### GitHub Actions (`.github/workflows/ci.yml`)

```
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│  backend-lint  │     │ backend-test   │     │ frontend-check │
│                │     │                │     │                │
│  ruff check    │     │  pytest        │     │  tsc           │
│  ruff format   │     │  --cov>=60%    │     │  next build    │
│   --check      │     │  Redis svc     │     │                │
└────────────────┘     └────────────────┘     └────────────────┘
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                ▼
                    ┌────────────────────┐
                    │   docker-build     │ (push only, not PRs)
                    │                    │
                    │  Matrix: backend,  │
                    │   frontend         │
                    │  GHA cache layers  │
                    └────────────────────┘
```

### Jobs Detail

| Job | Trigger | Python | Node | Services |
|-----|---------|--------|------|----------|
| `backend-lint` | Push + PR | 3.11 | — | — |
| `backend-test` | Push + PR | 3.11 | — | Redis 7 |
| `frontend-check` | Push + PR | — | 20 | — |
| `docker-build` | Push only | — | — | — |

### Coverage Threshold

```bash
pytest --cov=src --cov-report=term-missing --cov-fail-under=60
```

---

## 25. Testing Strategy

### Directory Structure

```
tests/
├── conftest.py                    # Shared fixtures (async client, app lifecycle)
├── test_applier.py                # Applier agent integration tests
├── test_live_applier_ws.py        # WebSocket applier tests
├── test_websocket_production.py   # Production WebSocket lifecycle tests
├── api/                           # API route tests
├── evals/                         # LLM-as-Judge evaluation tests
├── integration/                   # Cross-component tests
└── unit/
    ├── test_cache.py              # 8 tests — MemoryCache set/get/delete/model
    ├── test_config.py             # 8 tests — Settings validators, properties
    ├── test_exceptions.py         # 12 test classes — all 9 exception types
    ├── test_llm_provider.py       # 11 tests — backoff, config, rate limit detection
    ├── test_middleware.py         # 10 tests — security headers, size limit, correlation ID
    └── test_rate_limiter.py       # 7 tests — sliding window, isolation, expiry
```

### Test Fixtures

```python
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="module")
async def client():
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
```

### Test Patterns

| Pattern | Example | Purpose |
|---------|---------|---------|
| **Unit** | `test_exceptions.py` | Pure function testing, no I/O |
| **Starlette TestClient** | `test_middleware.py` | HTTP-level middleware testing |
| **WebSocket Testing** | `test_websocket_production.py` | Full WS lifecycle with `websockets` |
| **LLM Evals** | `evals/` | LLM-as-Judge output quality |

### WebSocket Production Tests

```python
class WebSocketTester:
    async def test_connection_lifecycle(self):
        # accept → ping/pong → graceful close

    async def test_heartbeat(self):
        # Verify server sends ping every 30s

    async def test_multiple_connections_prevented(self):
        # 5 concurrent connections to same session

    async def test_auth_failure(self):
        # Invalid token → close code 4001
```

---

## 26. Configuration Management

### `Settings` — Pydantic BaseSettings

All configuration via environment variables with type validation:

| Category | Key Fields |
|----------|-----------|
| **Environment** | `environment` (dev/staging/prod), `debug`, `log_level` |
| **Server** | `host`, `port`, `cors_origins`, `max_request_size` |
| **Rate Limiting** | `rate_limit_enabled`, `rate_limit_requests` (100), `rate_limit_period` (60s) |
| **Redis** | `redis_url` (Optional — graceful fallback without it) |
| **LLM Keys** | `groq_api_key`, `groq_api_key_fallback`, `openrouter_api_key`, `gemini_api_key` (all `SecretStr`) |
| **Models** | `groq_model`, `openrouter_model`, `gemini_model` |
| **Search** | `serpapi_api_key` |
| **Supabase** | `supabase_url`, `supabase_anon_key`, `supabase_service_key`, `supabase_jwt_secret` |
| **Browser** | `headless`, `chrome_path`, `user_data_dir`, `profile_directory` |
| **Security** | `encryption_key` (AES-256 for credential vault) |
| **Observability** | `phoenix_collector_endpoint` |
| **Celery** | `celery_broker_url`, `celery_result_backend` |

### Validators

```python
@field_validator("log_level")
def validate_log_level(cls, v):
    if v.upper() not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        raise ValueError(f"Invalid log level: {v}")
    return v.upper()

@field_validator("rate_limit_requests")
def validate_rate_limit_requests(cls, v):
    if v <= 0:
        raise ValueError("rate_limit_requests must be positive")
    return v
```

### Computed Properties

```python
@property
def is_production(self) -> bool:
    return self.environment == "production"

@property
def celery_broker(self) -> str:
    return self.celery_broker_url or self.redis_url or "redis://localhost:6379/0"

def get_cors_origins(self) -> list:
    return [o.strip() for o in self.cors_origins.split(",")]

def get_encryption_key(self) -> bytes:
    # Derives AES-256 key from encryption_key or JWT secret
    return hashlib.sha256(source.encode()).digest()
```

---

## 27. Dependency Map

### Core Framework

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.128.0 | Web framework |
| `uvicorn` | 0.40.0 | ASGI server |
| `gunicorn` | 21.2.0 | Process manager |
| `starlette` | 0.50.0 | HTTP toolkit |
| `pydantic` | 2.12.5 | Data validation |
| `pydantic-settings` | 2.12.0 | Configuration management |

### AI/ML Stack

| Package | Version | Purpose |
|---------|---------|---------|
| `langchain` | 1.2.6 | LLM orchestration framework |
| `langchain-groq` | 1.1.1 | Groq provider |
| `langchain-openai` | 1.1.7 | OpenAI/OpenRouter provider |
| `langchain-google-genai` | 4.2.0 | Gemini provider |
| `langchain-anthropic` | 1.3.1 | Claude provider |
| `langgraph` | 1.0.6 | Stateful agent workflows (DAG) |
| `langgraph-checkpoint` | 4.0.0 | LangGraph state persistence |

### Infrastructure

| Package | Version | Purpose |
|---------|---------|---------|
| `redis` | >=5.0.0 | Caching, rate limiting, pub/sub |
| `celery[redis]` | >=5.3.0 | Distributed task queue |
| `supabase` | 2.27.2 | Database + Auth + Storage |
| `structlog` | (latest) | Structured logging |

### Browser Automation

| Package | Version | Purpose |
|---------|---------|---------|
| `browser-use` | 0.11.2 | High-level browser control |
| `playwright` | 1.57.0 | Browser automation engine |

### Observability

| Package | Version | Purpose |
|---------|---------|---------|
| `arize-phoenix` | >=4.0.0 | LLM tracing dashboard |
| `openinference-instrumentation-langchain` | >=0.1.0 | Auto-instrumentation |
| `langsmith` | 0.6.2 | LLM experiment tracking |

---

## 28. Data Flow Diagrams

### Job Search → Application Flow

```
User clicks "Search Jobs"
         │
         ▼
    POST /api/v1/jobs/search
         │
         ▼
    ┌──────────────┐
    │  ScoutAgent   │ SerpAPI Google search for ATS URLs
    └──────┬───────┘
           │ URLs[]
           ▼
    Persist to Supabase (discovered_jobs)
         │
         ▼
    POST /api/v1/jobs/analyze/{id}
         │
         ▼
    ┌──────────────┐
    │AnalystAgent   │ Scrape + LLM extract → match_score
    └──────┬───────┘
           │ JobAnalysis
           ▼
    POST /api/v1/jobs/apply/{id}
         │
         ├── trigger_agent=false → Save as "pending" in DB
         │
         └── trigger_agent=true
              │
              ▼
         Celery task.delay()
              │
              ▼
         ┌──────────────┐
         │  ApplierAgent │ Playwright + Gemini Vision
         │  (Celery Worker)│
         └──────────────┘
              │
              ▼
         Redis pub/sub → WebSocket → Client UI (screenshots, progress)
```

### Pipeline Orchestration Flow

```
WS /ws/{session_id} → message: { type: "start_pipeline", query, location }
         │
         ▼
    ┌──────────────────────────────────────────┐
    │     StreamingPipelineOrchestrator          │
    │                                           │
    │  1. Load User Profile (Supabase/YAML)     │
    │  2. Scout → discover URLs                 │
    │                                           │
    │  ┌─── Per URL Loop ─────────────────────┐ │
    │  │ 3. Analyst → analyze + match_score   │ │
    │  │    (skip if score < threshold)        │ │
    │  │ 4. Company → research                 │ │
    │  │ 5. Resume → tailor (+ HITL)           │ │
    │  │ 6. Cover Letter → generate (LangGraph)│ │
    │  │ 7. Applier → submit (+ draft HITL)    │ │
    │  └──────────────────────────────────────┘ │
    │                                           │
    │  8. PIPELINE_COMPLETE event               │
    └──────────────────────────────────────────┘
         │
    (All events streamed via WebSocket in real-time)
```

### Authentication Flow

```
┌──────────┐                    ┌──────────┐                    ┌──────────┐
│  Client   │                    │  FastAPI  │                    │ Supabase │
│ (Next.js) │                    │  Backend  │                    │   Auth   │
└─────┬────┘                    └─────┬────┘                    └─────┬────┘
      │                              │                               │
      │  1. Login (email/password)   │                               │
      │─────────────────────────────────────────────────────────────▶│
      │                              │                               │
      │  2. JWT Token                │                               │
      │◀─────────────────────────────────────────────────────────────│
      │                              │                               │
      │  3. API Request              │                               │
      │  Authorization: Bearer {jwt} │                               │
      │─────────────────────────────▶│                               │
      │                              │  4. Decode JWT                │
      │                              │  (HS256: local secret)       │
      │                              │  (ES256: fetch JWKS)         │
      │                              │─────────────────────────────▶│
      │                              │◀─────────────────────────────│
      │                              │                               │
      │                              │  5. Extract user_id, email   │
      │                              │  6. Check per-user rate limit│
      │                              │  7. Process request          │
      │  8. Response                 │                               │
      │◀─────────────────────────────│                               │
```

---

## Architecture Highlights for System Design Interviews

| Concept | Implementation in This Project |
|---------|-------------------------------|
| **Multi-Provider Failover** | 5-deep LLM fallback chain across Groq, OpenRouter, Gemini |
| **Circuit Breaker** | Tri-state (Closed/Open/Half-Open) with configurable thresholds |
| **CQRS-like Separation** | Read-heavy endpoints (jobs list) vs. write-heavy (pipeline start) |
| **Event-Driven Architecture** | 40+ WebSocket event types, Redis pub/sub for worker bridging |
| **Saga Pattern** | Pipeline orchestrator with compensation (stop/pause mid-pipeline) |
| **HITL Design** | Future-based async with 300s timeout, Redis bridging for workers |
| **Strategy Pattern** | Rate limiter (Memory vs Redis), Cache (Redis vs in-memory) |
| **Factory Pattern** | Agent lazy-loading, LLM provider creation |
| **Chain of Responsibility** | LLM provider fallback, middleware stack |
| **State Machine** | LangGraph cover letter DAG, circuit breaker states |
| **Graceful Degradation** | Redis optional, cache fallback, rate limiter fail-open |
| **Multi-Tenancy** | User-scoped data (RLS + application-level user_id filtering) |
| **API Versioning** | `/api/v1/` canonical + legacy backward compat |
| **12-Factor App** | Env-based config, stateless processes, backing services |
| **Correlation IDs** | UUID-based X-Request-ID across full request lifecycle |
| **Cost Observability** | Per-invocation token/cost tracking with agent attribution |

---

## Quick Start

```bash
# 1. Clone & install
cd backend
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Run development server
uvicorn src.main:app --reload --port 8000

# 4. Run with Docker
docker compose up --build

# 5. Run tests
pytest tests/unit/ -v

# 6. Run Celery worker (for browser automation)
celery -A worker.celery_app worker -Q browser --loglevel=info --pool=solo
```

---

*Built with FastAPI, LangChain, LangGraph, Playwright, Supabase, Redis, and Celery.*
