# JobStream — Advanced System Design & Architecture

> **Date:** March 2026  
> **Stack:** FastAPI · LangGraph · Next.js 14 · Supabase · browser-use · Groq / OpenRouter / Gemini  
> **Status:** Production-ready multi-tenant AI career automation platform

---

## Table of Contents

1. [Executive Overview](#1-executive-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Frontend Architecture](#3-frontend-architecture)
4. [Backend Architecture](#4-backend-architecture)
5. [AI Agent Layer](#5-ai-agent-layer)
6. [Automator Layer (Pipeline Workers)](#6-automator-layer-pipeline-workers)
7. [LangGraph Pipeline State Machine](#7-langgraph-pipeline-state-machine)
8. [Database Design](#8-database-design)
9. [Real-Time WebSocket Architecture](#9-real-time-websocket-architecture)
10. [LLM Provider Fallback Chain](#10-llm-provider-fallback-chain)
11. [Core Infrastructure Systems](#11-core-infrastructure-systems)
12. [Security & Auth Architecture](#12-security--auth-architecture)
13. [Observability & Monitoring](#13-observability--monitoring)
14. [User Journey Flows](#14-user-journey-flows)
15. [Data Flow: Job Application Pipeline](#15-data-flow-job-application-pipeline)
16. [Inter-Agent Communication Protocol](#16-inter-agent-communication-protocol)
17. [Deployment Architecture](#17-deployment-architecture)

---

## 1. Executive Overview

JobStream is a **full-stack AI career automation platform** that acts as an autonomous job application command centre. It orchestrates multiple specialised AI agents — each an expert in a narrow domain — across a LangGraph state machine pipeline, exposing a real-time Next.js dashboard for human-in-the-loop oversight.

### Core Capabilities

| Capability | Technology | Description |
|---|---|---|
| Autonomous job discovery | ScoutAgent + SerpAPI | Searches Greenhouse, Lever, Ashby ATS platforms |
| Resume-to-job matching | AnalystAgent + Groq LLaMA-3 | Per-job match score, gap analysis, skill diff |
| Resume tailoring | ResumeAgent | ATS-optimised LaTeX resume generation |
| Cover letter generation | CoverLetterAgent | Company-aware personalised letters |
| Company intelligence | CompanyAgent | Dossiers, culture, red flags, interview tips |
| Live browser application | ApplierAgent + browser-use | Actual form-filling via headless Chromium |
| Human-in-the-loop | WebSocket HITL | Real-time override at any pipeline node |
| Network outreach | NetworkAgent | LinkedIn connection research + message templates |
| Interview preparation | InterviewAgent | Role-specific Q&A, STAR answers, coaching |
| Salary negotiation | SalaryService | Benchmarking, offer analysis, counter scripts |
| Career path planning | CareerTrajectory | Skills gap map, timeline projections |
| Application tracking | TrackerAgent | Full lifecycle from lead to offer |
| RAG profile enrichment | RAGService + pgvector | Semantic resume/profile search |

---

## 2. High-Level Architecture

```mermaid
graph TB
    subgraph CLIENT["Client Layer (Next.js 14)"]
        UI[React Dashboard]
        WS_CLIENT[WebSocket Client]
        AUTH_UI[Auth UI]
    end

    subgraph GATEWAY["API Gateway (FastAPI)"]
        REST[REST Endpoints\n/api/v1/*]
        WS_SERVER[WebSocket Manager\n/ws/:session_id]
        MIDDLEWARE[Middleware Stack\nAuth - Rate Limit - Credits - Security]
    end

    subgraph AGENT_LAYER["AI Agent Layer"]
        RESUME_A[ResumeAgent]
        COVER_A[CoverLetterAgent]
        COMPANY_A[CompanyAgent]
        INTERVIEW_A[InterviewAgent]
        NETWORK_A[NetworkAgent]
        TRACKER_A[TrackerAgent]
    end

    subgraph AUTOMATOR_LAYER["Automator Layer (Pipeline Nodes)"]
        SCOUT[ScoutAgent\nJob Discovery]
        ANALYST[AnalystAgent\nJob Matching]
        APPLIER[ApplierAgent\nBrowser Automation]
    end

    subgraph PIPELINE["LangGraph State Machine"]
        GRAPH[Pipeline Graph\n7-node DAG]
    end

    subgraph CORE["Core Infrastructure"]
        LLM[Unified LLM\nGroq→OpenRouter→Gemini]
        CACHE[Cache\nRedis / Memory]
        CB[Circuit Breaker]
        MEM[Agent Memory]
        PROTO[Agent Protocol\nEvent Bus]
        GUARD[Guardrails\nPII - Injection - Schema]
    end

    subgraph STORAGE["Storage Layer"]
        SUPA[Supabase PostgreSQL\n+ RLS + PostgREST]
        VECTOR[pgvector\nRAG Embeddings]
        FILES[Supabase Storage\nResume PDFs]
    end

    UI --> REST
    WS_CLIENT --> WS_SERVER
    AUTH_UI --> SUPA

    REST --> MIDDLEWARE
    MIDDLEWARE --> AGENT_LAYER
    MIDDLEWARE --> PIPELINE
    WS_SERVER --> PIPELINE

    AGENT_LAYER --> CORE
    AUTOMATOR_LAYER --> CORE
    PIPELINE --> AUTOMATOR_LAYER

    CORE --> STORAGE
    AGENT_LAYER --> STORAGE
```

---

## 3. Frontend Architecture

```mermaid
graph TD
    subgraph PAGES["Next.js App Router"]
        ROOT["/app/page.tsx\nEntry Point + Auth Guard"]
        TEST["/app/test-dashboard/\nHealth Monitor"]
    end

    subgraph AUTH_LAYER["Auth Flow"]
        AUTH_COMP[AuthPanel\nEmail/OTP Login]
        SUPABASE_CLIENT[supabase.ts\nAnon Key Client]
    end

    subgraph WORKSPACE["Product Workspace"]
        PW[ProductWorkspace.tsx\nOrchestrator Shell]
        COMPLETION[ProfileCompletionPanel\nOnboarding Gate]
        SIDEBAR[Sidebar.tsx\n13-panel Navigation]
        TOPBAR[Topbar.tsx\nCredits - WS Status]
    end

    subgraph PANELS["Feature Panels (13)"]
        direction LR
        PP[PipelinePanel\nFull Automation]
        LA[LiveAgentPanel\nBrowser Stream]
        JP[JobsPanel\nSearch + Analyze]
        RP[ResumePanel\nATS Studio]
        CL[CoverLetterPanel]
        CO[CompanyPanel\nDossiers]
        IP[InterviewPanel]
        TP[TrackerPanel]
        NP[NetworkPanel\nReferrals]
        CAP[CareerPanel\nPaths + Gaps]
        PROF[ProfilePanel\nView + Edit]
        AN[AnalyticsPanel\nMetrics]
        T[TestDashboard\nHealth Checks]
    end

    subgraph HOOKS["Custom Hooks"]
        UA[useAuth\nSession Management]
        RTA[useRealtimeApplier\nWebSocket Client]
        PSH[usePipelineSocket\nPrimary WS Hook]
    end

    subgraph API_CLIENT["API Client"]
        AC[api-client.ts\napiRequest T]
    end

    ROOT --> AUTH_COMP
    ROOT --> WORKSPACE
    AUTH_COMP --> SUPABASE_CLIENT
    PW --> COMPLETION
    PW --> SIDEBAR
    PW --> TOPBAR
    PW --> PANELS
    PW --> HOOKS
    PANELS --> AC
    AC --> |"Bearer JWT\n→ http://localhost:8000"| BACKEND((FastAPI))
    HOOKS --> |"wss://"|WS((WebSocket))
```

### State Flow in ProductWorkspace

```mermaid
stateDiagram-v2
    [*] --> LoadingProfileCompletion
    LoadingProfileCompletion --> ShowOnboardingGate : has_profile = false
    LoadingProfileCompletion --> ActiveWorkspace : has_profile = true
    ShowOnboardingGate --> CreatingProfile : User submits form
    CreatingProfile --> ActiveWorkspace : POST /api/v1/user/profile success
    ActiveWorkspace --> PanelSwitch : Sidebar click
    PanelSwitch --> ActiveWorkspace : Panel renders
    ActiveWorkspace --> [*] : Sign Out
```

---

## 4. Backend Architecture

```mermaid
graph TD
    subgraph ENTRY["Entry Point: main.py"]
        LIFESPAN["Lifespan Manager\nStartup and Shutdown"]
        APP["FastAPI App"]
        ROUTES["Route Registration\n15 route groups"]
    end

    subgraph MIDDLEWARE_STACK["Middleware Stack in order"]
        M1["CORSMiddleware\nOrigin whitelist"]
        M2["SecurityHeadersMiddleware\nCSP, HSTS, X-Frame"]
        M3["RequestSizeLimitMiddleware\n10 MB max body"]
        M4["RequestLoggingMiddleware\nStructured access logs"]
        M5["RateLimitMiddleware\nIn-memory sliding window"]
        M6["ProductionRateLimitMiddleware\nPer-route burst protection"]
        M7["CreditGuardrailMiddleware\nQuery and token budget enforcement"]
    end

    subgraph ROUTE_GROUPS["API Route Groups api/v1"]
        R1["user: Profile CRUD\nOnboarding, Completion, Readiness"]
        R2["jobs: Scout + Analyst\nSearch, Analyze, Discover"]
        R3["resume: ATS Studio\nUpload, Tailor, Generate, Download"]
        R4["cover-letter: Generation\nCustom, Company-Aware"]
        R5["company: Intel\nDossier, Culture, Risks, Interview Tips"]
        R6["interview: Prep\nQuestions, STAR, Roleplay"]
        R7["network: Outreach\nLeads, Messages, LinkedIn"]
        R8["tracker: Applications\nPipeline, Status, Notes"]
        R9["career: Trajectory\nPaths, Gaps, Timeline"]
        R10["salary: Benchmarks\nOffers, Negotiation"]
        R11["pipeline: Full Run\nLangGraph execution"]
        R12["analytics: Metrics\nCredits, Costs, Health"]
        R13["rag: Vector Search\nIndex, Query, Sync"]
        R14["agents: Protocol\nMemory, Feedback, Insights"]
        R15["chat: Orchestrator\nMulti-Agent Chat"]
    end

    ENTRY --> MIDDLEWARE_STACK
    MIDDLEWARE_STACK --> ROUTE_GROUPS
```

### Request Lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant CORS
    participant Security
    participant RateLimit
    participant Credits
    participant Auth
    participant RouteHandler
    participant Service
    participant Supabase

    Client->>CORS: HTTP Request
    CORS->>Security: Add security headers
    Security->>RateLimit: Check rate window
    RateLimit-->>Client: 429 if exceeded
    RateLimit->>Credits: Check daily budget
    Credits-->>Client: 402 if budget exhausted
    Credits->>Auth: Verify JWT (ES256)
    Auth-->>Client: 401 if invalid
    Auth->>RouteHandler: AuthUser injected via Depends()
    RouteHandler->>Service: Business logic
    Service->>Supabase: DB query (admin client, RLS bypassed)
    Supabase-->>Service: Result
    Service-->>RouteHandler: Domain object
    RouteHandler-->>Client: JSON response + credit headers
```

---

## 5. AI Agent Layer

Six specialised agents, each encapsulating a narrow domain of expertise. All inherit from a common protocol and share agent memory.

```mermaid
graph LR
    subgraph AGENTS["Domain Agents (src/agents/)"]
        direction TB
        RA["ResumeAgent\n— ATS scoring\n— LaTeX generation\n— Tailoring for JD"]
        CA["CompanyAgent\n— Company dossiers\n— Culture analysis\n— Red flag detection\n— Interview tip sets"]
        CLA["CoverLetterAgent\n— Personalised letters\n— Company-aware tone\n— JD keyword inject"]
        IA["InterviewAgent\n— Q&A generation\n— STAR coaching\n— Technical drills\n— Role play sessions"]
        NA["NetworkAgent\n— LinkedIn lead search\n— Referral paths\n— Outreach messages\n— Connection templates"]
        TA["TrackerAgent\n— Application states\n— Follow-up reminders\n— Offer comparison\n— Pipeline analytics"]
    end

    subgraph SHARED["Shared Infrastructure"]
        LLM2[UnifiedLLM\nFallback Provider]
        MEM2[AgentMemory\nPreference + Feedback]
        PROTO2[AgentProtocol\nBroadcast + Request]
        GUARD2[Guardrails\nInput/Output Safety]
        RAG2[RAGService\nProfile + Resume Index]
    end

    AGENTS --> SHARED
```

### Agent Memory System

```mermaid
graph TD
    subgraph MEMORY["AgentMemory — Two-Tier Storage"]
        FAST["L1: Redis (optional)\nTTL-based ephemeral cache\nActive session context"]
        DURABLE["L2: Supabase\nagent_memories table\nLong-term preferences"]
        FEEDBACK["Feedback Loop\nRating 1-5 → AgentInsight\nImproves future outputs"]
    end

    subgraph TYPES["Memory Types"]
        PREF[PREFERENCE\nUser style preferences]
        LEARN[LEARNING\nDistilled insights]
        CTX[CONTEXT\nSession context]
        FB2[FEEDBACK\nQuality ratings]
        PERF[PERFORMANCE\nAgent metrics]
    end

    Agent --> |remember / recall| FAST
    FAST --> |miss / TTL| DURABLE
    Agent --> |record_feedback| FEEDBACK
    FEEDBACK --> LEARN
    MEMORY --> TYPES
```

---

## 6. Automator Layer (Pipeline Workers)

Three specialised automators form the core pipeline execution units.

```mermaid
graph TD
    subgraph AUTOMATORS["src/automators/"]
        BASE["BaseAgent\n— Settings access\n— Logging setup\n— Shared utilities"]

        SCOUT["ScoutAgent\n─────────────────\n• SerpAPI → Google Jobs\n• ATS domain targeting\n  (Greenhouse, Lever, Ashby)\n• Groq LLaMA-3.3 70B\n  reflection/self-correction\n• Retry on empty results\n• Returns List[ScrapedJob]"]

        ANALYST["AnalystAgent\n─────────────────\n• BeautifulSoup HTML scrape\n• JD text extraction (20k chars)\n• Groq JSON completion\n• Pydantic JobAnalysis model\n• Outputs:\n  - match_score (0-100)\n  - matching_skills[]\n  - missing_skills[]\n  - gap_analysis_advice\n  - tech_stack[]\n  - salary range\n  - reasoning"]

        APPLIER["ApplierAgent\n─────────────────\n• browser-use framework\n• Real Chromium (ProactorEventLoop)\n• Screenshot streaming → WS\n• HITL: ask_human() tool\n• Draft Mode (pause before submit)\n• Per-user profile injection\n• Multi-field form filling\n• Resume PDF upload"]
    end

    BASE --> SCOUT
    BASE --> ANALYST
    BASE --> APPLIER
```

### Scout Agent Flow

```mermaid
flowchart TD
    START([ScoutAgent.run]) --> QUERY[Build ATS-targeted query\nsite:greenhouse.io OR lever.co OR ashbyhq.com]
    QUERY --> SERPAPI[SerpAPI Google Search\nwith date filter tbs=qdr:m]
    SERPAPI --> RESULTS{Results?}
    RESULTS -- Empty --> REFLECT[LLM Self-Reflection\nRewrite query]
    REFLECT --> |Attempt 2| SERPAPI
    REFLECT --> |Attempt > 2| EMPTY[Return empty list]
    RESULTS -- Found --> FILTER[Filter: only valid ATS URLs\nDe-duplicate]
    FILTER --> JOBS[Build List&lt;ScrapedJob&gt;\nurl, domain, title, company, status]
    JOBS --> WEBHOOK{webhook_url?}
    WEBHOOK -- Yes --> POST[POST results instantly\nto webhook endpoint]
    WEBHOOK -- No --> RETURN([Return ScrapedJob list])
    POST --> RETURN
```

### Analyst Agent Flow

```mermaid
flowchart TD
    START([AnalystAgent.run]) --> FETCH[HTTP GET job URL\nUser-Agent spoofed\nTimeout: 10s]
    FETCH --> PARSE[BeautifulSoup parse\nRemove script/style/nav\nClean text max 20k chars]
    PARSE --> PROMPT[Build Groq prompt\nJD text + Resume text]
    PROMPT --> LLM_CALL[Groq LLaMA-3.3 70B\nTemperature: 0.0\nJSON-only output]
    LLM_CALL --> VALIDATE[Pydantic JobAnalysis\nStrict schema validation]
    VALIDATE --> SCORE{match_score}
    SCORE -- Below threshold --> SKIP[Emit: skip event\nContinue pipeline]
    SCORE -- Above threshold --> PROCEED[Emit: analyze:result\nContinue to apply]
```

---

## 7. LangGraph Pipeline State Machine

The autonomous pipeline is a **7-node directed acyclic graph** built with LangGraph, with conditional edges, parallel execution, HITL checkpoints, and disk-based checkpoint resume.

```mermaid
stateDiagram-v2
    [*] --> scout_jobs : start_pipeline()
    scout_jobs --> analyze_jobs : Jobs found
    scout_jobs --> [*] : No jobs / error

    analyze_jobs --> research_company : match_score ≥ threshold\n+ use_company_research=true
    analyze_jobs --> tailor_resume : match_score ≥ threshold\n+ use_company_research=false
    analyze_jobs --> [*] : All jobs below threshold

    research_company --> tailor_resume : Company dossier ready

    state parallel_state <<fork>>
    tailor_resume --> parallel_state : use_resume_tailoring=true
    parallel_state --> generate_resume : Parallel branch A
    parallel_state --> generate_cover_letter : Parallel branch B

    state parallel_join <<join>>
    generate_resume --> parallel_join
    generate_cover_letter --> parallel_join

    parallel_join --> apply_job : auto_apply=true
    parallel_join --> [*] : auto_apply=false

    apply_job --> [*] : Complete / Error
    apply_job --> analyze_jobs : next job (loop)
```

### Pipeline State Schema

```mermaid
classDiagram
    class PipelineState {
        +str query
        +str location
        +int min_match_score
        +int max_jobs
        +bool auto_apply
        +bool use_company_research
        +bool use_resume_tailoring
        +bool use_cover_letter
        +str session_id
        +str user_id
        +str profile_source
        +str resume_text
        +List[str] job_urls
        +int current_job_index
        +List[JobResult] job_results
        +Dict node_statuses
        +int total_analyzed
        +int total_applied
        +int total_skipped
        +bool is_running
        +Optional[str] error
        +Optional[str] hitl_response
    }

    class NodeStatus {
        <<enumeration>>
        PENDING
        RUNNING
        SKIPPED
        COMPLETE
        ERROR
    }

    class PipelineCheckpoint {
        +str session_id
        +Path _path
        +save(state, completed_node)
        +load() Optional[dict]
        +clear()
    }

    PipelineState --> NodeStatus
    PipelineState --> PipelineCheckpoint
```

### Checkpoint Recovery Flow

```mermaid
sequenceDiagram
    participant Client
    participant PipelineAPI
    participant CheckpointStore
    participant LangGraph

    Client->>PipelineAPI: POST /pipeline/run {session_id}
    PipelineAPI->>CheckpointStore: load(session_id)
    CheckpointStore-->>PipelineAPI: checkpoint / None

    alt Checkpoint exists
        PipelineAPI->>LangGraph: resume from _checkpoint_node
        LangGraph->>LangGraph: skip completed nodes
    else No checkpoint
        PipelineAPI->>LangGraph: start from scout_jobs
    end

    LangGraph-->>PipelineAPI: emit events via WebSocket
    LangGraph->>CheckpointStore: save(state, node) after each node
    LangGraph-->>Client: stream events real-time
    LangGraph->>CheckpointStore: clear() on completion
```

---

## 8. Database Design

### Entity Relationship Overview

```mermaid
erDiagram
    auth_users ||--|| user_profiles : "1-to-1"
    user_profiles ||--o{ user_resumes : "1-to-many"
    user_profiles ||--o{ agent_memories : "1-to-many"
    user_profiles ||--o{ user_feedback : "1-to-many"
    user_profiles ||--o{ network_leads : "1-to-many"
    user_profiles ||--o{ company_reports : "1-to-many"
    user_profiles ||--o{ interview_sessions : "1-to-many"
    user_profiles ||--o{ salary_analyses : "1-to-many"
    user_profiles ||--o{ discovered_jobs : "1-to-many"
    user_profiles ||--o{ resume_documents : "1-to-many"
    user_profiles ||--o{ cover_letters : "1-to-many"

    user_profiles {
        uuid id PK
        uuid user_id FK
        varchar first_name
        varchar last_name
        varchar email
        varchar phone
        varchar linkedin_url
        varchar github_url
        varchar portfolio_url
        jsonb personal_info
        jsonb skills
        jsonb education
        jsonb experience
        jsonb projects
        boolean onboarding_completed
        timestamptz created_at
        timestamptz updated_at
    }

    user_resumes {
        uuid id PK
        uuid user_id FK
        text content
        varchar filename
        boolean is_primary
        jsonb metadata
        timestamptz created_at
    }

    agent_memories {
        uuid id PK
        varchar agent_name
        uuid user_id FK
        varchar key
        jsonb value
        varchar memory_type
        float confidence
        int access_count
        timestamptz expires_at
    }

    discovered_jobs {
        uuid id PK
        uuid user_id FK
        varchar url
        varchar title
        varchar company
        varchar status
        int match_score
        jsonb analysis
        timestamptz created_at
    }
```

### JSONB Column Architecture

The profile uses embedded JSONB for structured sub-objects — avoiding excessive joins for read-heavy profile lookups:

```mermaid
graph LR
    subgraph user_profiles
        PI["personal_info JSONB\n• first_name, last_name\n• email, phone\n• location (city/country)\n• summary\n• linkedin_url, github_url\n• portfolio_url"]
        SK["skills JSONB\n{ primary: [...],\n  secondary: [...],\n  tools: [...] }"]
        EDU["education JSONB Array\n[{ degree, major, university,\n   start_date, end_date, cgpa,\n   is_current }]"]
        EXP["experience JSONB Array\n[{ title, company,\n   start_date, end_date,\n   is_current, description }]"]
        PROJ["projects JSONB Array\n[{ name, tech_stack[],\n   description, project_url }]"]
    end
```

### Row Level Security (RLS) Policy Pattern

```mermaid
graph TD
    REQUEST[Any DB Request] --> RLS{RLS Policy Check}
    RLS --> |"auth.uid() = user_id"| ALLOW[Allow Read/Write]
    RLS --> |"No match"| DENY[Deny — 0 rows returned]

    BACKEND[Backend Admin Client\nSUPABASE_SERVICE_KEY] --> |"Bypasses RLS\nService Role"| DIRECT[Direct DB access]
    FRONTEND[Frontend\nAnon Key] --> |"Through PostgREST\nRLS enforced"| RLS
```

### pgvector RAG Architecture

```mermaid
graph LR
    subgraph RAG["RAGService — Retrieval-Augmented Generation"]
        EMBED["text-embedding-3-small\n(OpenAI / compatible)"]
        CHUNK["Text Chunker\nResume → 512-token chunks"]
        STORE["pgvector table\nresume_embeddings\n(vector 1536-dim)"]
        QUERY["Similarity Search\nCosine distance <=> operator"]
        RETRIEVE["Top-K chunks\nfor agent context injection"]
    end

    RESUME[Resume Text] --> CHUNK
    CHUNK --> EMBED
    EMBED --> STORE
    USER_QUERY["Job Description text"] --> EMBED
    STORE --> |"SELECT ... ORDER BY\nvector <=> $1"| QUERY
    QUERY --> RETRIEVE
    RETRIEVE --> |"Context injection"| AGENTS[AI Agents]
```

---

## 9. Real-Time WebSocket Architecture

```mermaid
graph TD
    subgraph WS_SERVER["WebSocket Manager (server)"]
        CONN_TABLE["Connection Registry\nDict[session_id → WebSocket]"]
        EVENT_HIST["Event History\ndeque(maxlen=100) per session"]
        BROADCAST["broadcast(session_id, event)"]
        HITL_GATE["HITL Gating\nFuture-based async pause"]
    end

    subgraph EVENT_TYPES["WebSocket Event Types"]
        direction LR
        PIPELINE_EVT["Pipeline Events\npipeline:start/complete/error"]
        SCOUT_EVT["Scout Events\nscout:start/searching/found"]
        ANALYST_EVT["Analyst Events\nanalyst:result/skip"]
        COMPANY_EVT["Company Events\ncompany:researching/result"]
        RESUME_EVT["Resume Events\nresume:tailoring/generated"]
        COVER_EVT["Cover Letter Events\ncover_letter:generating/complete"]
        APPLIER_EVT["Applier Events\napplier:navigate/click/type/screenshot"]
        DRAFT_EVT["Draft Events\ndraft:review/confirm/edit"]
        HITL_EVT["HITL Events\nhitl:request/response"]
        BROWSER_EVT["Browser Events\nbrowser:screenshot (base64 JPG)"]
        CHAT_EVT["Chat Events\nchat:message (bidirectional)"]
        TASK_EVT["Task Events\ntask:queued/started/progress/complete"]
    end

    PIPELINE --> |"emit events"| BROADCAST
    BROADCAST --> WS_CLIENT["Frontend useRealtimeApplier hook"]

    subgraph HITL_FLOW["HITL Flow"]
        AGENT_PAUSE["Agent hits ask_human()"] --> CREATE_FUTURE["asyncio.Future created"]
        CREATE_FUTURE --> EMIT_HITL["emit hitl:request to client\nquestion + hitl_id"]
        EMIT_HITL --> WAIT["await future - blocking agent"]
        CLIENT_REPLY["User types response\nFrontend sends hitl:response"] --> RESOLVE["future.set_result(answer)"]
        RESOLVE --> AGENT_RESUME["Agent receives answer\ncontinues execution"]
    end

    subgraph SCREENSHOT_STREAMING["Live Screenshot Streaming"]
        BROWSER_LOOP["Screenshot loop\nevery 1-2 seconds"] --> CAPTURE["browser.take_screenshot()\nJPEG base64"]
        CAPTURE --> WS_EMIT["emit browser:screenshot\nimage: base64 JPEG"]
        WS_EMIT --> FRONTEND_RENDER["Frontend renders\nlive image frame"]
    end
```

### WebSocket Message Protocol

```mermaid
classDiagram
    class AgentEvent {
        +EventType type
        +str agent
        +Optional[str] message
        +Optional[dict] data
        +Optional[str] session_id
        +str timestamp
    }

    class EventType {
        <<enumeration>>
        PIPELINE_START
        PIPELINE_COMPLETE
        SCOUT_FOUND
        ANALYST_RESULT
        COMPANY_RESULT
        RESUME_GENERATED
        COVER_LETTER_COMPLETE
        APPLIER_SCREENSHOT
        DRAFT_REVIEW
        HITL_REQUEST
        HITL_RESPONSE
        BROWSER_SCREENSHOT
        CHAT_MESSAGE
        TASK_QUEUED
        TASK_COMPLETE
    }
```

---

## 10. LLM Provider Fallback Chain

```mermaid
graph TD
    subgraph UNIFIED_LLM["UnifiedLLM — Multi-Provider Cascade"]
        P1["Provider 1: Groq Primary\nllama-3.3-70b (fastest)"]
        P2["Provider 2: Groq Fallback\nbackup API key"]
        P3["Provider 3: OpenRouter Primary\nclaude-3-sonnet / gpt-4o"]
        P4["Provider 4: OpenRouter Fallback\nbackup OR key"]
        P5["Provider 5: Gemini\ngemini-1.5-pro (final fallback)"]

        P1 --> |"RateLimitError\nor APIError"| P2
        P2 --> |"failure"| P3
        P3 --> |"failure"| P4
        P4 --> |"failure"| P5
        P5 --> |"all fail"| ERR[Raise LLMError]
    end

    subgraph RETRY["Retry Logic"]
        EXP["Exponential Backoff\nbase=1s, max=60s\nmax_retries=3"]
    end

    subgraph CB2["Circuit Breaker (per provider)"]
        CLOSED["CLOSED\n(normal)"]
        OPEN["OPEN\n(fail-fast)"]
        HALF["HALF_OPEN\n(probe)"]

        CLOSED --> |"≥ N failures"| OPEN
        OPEN --> |"recovery_timeout elapsed"| HALF
        HALF --> |"probe succeeds"| CLOSED
        HALF --> |"probe fails"| OPEN
    end

    UNIFIED_LLM --> RETRY
    UNIFIED_LLM --> CB2
```

### Model Routing Policy

```mermaid
graph LR
    TASK{Task Type} --> |"Speed critical\nSimple extraction"| GROQ_FAST[Groq LLaMA-3.3 70B\nSub-second inference]
    TASK --> |"Complex reasoning\nCreative writing"| OR[OpenRouter\nClaude-3/GPT-4o]
    TASK --> |"Long context\nDocument analysis"| GEM[Gemini 1.5 Pro\n1M context window]
    TASK --> |"Embeddings"| EMBED_MODEL[text-embedding-3-small\nOpenAI API]
```

---

## 11. Core Infrastructure Systems

### DI Container Architecture

```mermaid
graph LR
    subgraph CONTAINER["DI Container (src/core/container.py)"]
        SINGLETON["register_singleton(name, factory)\nLazy-init, one instance"]
        INSTANCE["register_instance(name, obj)\nPre-built object"]
        RESOLVE["resolve(name)\nGet dependency"]
    end

    subgraph REGISTERED["Registered Services"]
        EB[event_bus]
        PII[pii_detector]
        IG[input_guardrails]
        CG[chat_guardrails]
        OG[output_guardrails]
        AM[agent_memory]
        CT[cost_tracker]
        SL[structured_logger]
        RB[retry_budget]
        AP[agent_protocol]
    end

    CONTAINER --> REGISTERED
```

### Caching Architecture

```mermaid
graph TD
    subgraph CACHE["Cache Layer (cache.py)"]
        CHECK_REDIS{REDIS_URL\nconfigured?}
        CHECK_REDIS -- Yes --> REDIS["Redis Client\nasync aioredis\nTTL support"]
        CHECK_REDIS -- No --> MEMORY["In-Memory Dict\nTTL-based\nThread-safe"]
    end

    subgraph CACHE_OPS["Cache Operations"]
        GET["get(key) → Optional[V]"]
        SET["set(key, value, ttl)"]
        DEL["delete(key)"]
        GET_MODEL["get_model(key, Model)\nPydantic deserialize"]
        SET_MODEL["set_model(key, obj, ttl)\nPydantic serialize"]
    end

    CACHE --> CACHE_OPS

    subgraph CACHED_DATA["What Is Cached"]
        PROFILE_CACHE["User Profiles\nTTL: 5min\nKey: profile:user_id"]
        LLM_CACHE["LLM Responses\nTTL: 1h\nKey: llm:prompt_hash"]
        COMPANY_CACHE["Company Dossiers\nTTL: 24h\nKey: company:name"]
    end
```

### Rate Limiting Architecture

```mermaid
graph TD
    subgraph RATELIMIT["Multi-Layer Rate Limiting"]
        L1["Layer 1: RateLimitMiddleware\nGlobal: 100 req/60s per IP\nIn-memory sliding window"]
        L2["Layer 2: ProductionRateLimitMiddleware\nPer-route burst protection\nCustom limits per endpoint"]
        L3["Layer 3: rate_limit_check Dependency\nPer-user JWT-based\nApplied to write operations"]
        L4["Layer 4: CreditGuardrailMiddleware\nPer-user daily query budget\nPer-user daily token budget"]
    end

    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> HANDLER[Route Handler]
```

### Guardrails Pipeline

```mermaid
graph LR
    subgraph INPUT_PIPELINE["Input Guardrail Pipeline"]
        IS["InputSanitizer\nStrip HTML, normalize whitespace"]
        PID["PromptInjectionDetector\nPattern: ignore/bypass/jailbreak\nHeuristic scoring"]
        PII2["PIIDetector\nEmail/Phone/SSN/CC masking"]
    end

    subgraph OUTPUT_PIPELINE["Output Guardrail Pipeline"]
        OV["OutputValidator\nPydantic schema enforcement"]
        CS["ContentSafety\nToxicity filter for chat"]
    end

    USER_INPUT --> IS --> PID --> PII2 --> AGENT
    AGENT_OUTPUT --> OV --> CS --> USER_RESPONSE

    style PID fill:#f9a,stroke:#f33
    style OV fill:#adf,stroke:#33f
```

### Idempotency & Distributed Locking

```mermaid
graph TD
    subgraph IDEMP["Idempotency (idempotency.py)"]
        IKEY["Idempotency-Key header\nUUID from client"]
        ISTORE["Redis/Memory store\nkey → result, 24h TTL"]
        ICHECK{Key seen before?}
        ICHECK -- Yes --> REPLAY[Return cached result\nno re-execution]
        ICHECK -- No --> EXEC[Execute + store result]
    end

    subgraph DLOCK["Distributed Lock (distributed_lock.py)"]
        LOCK["Acquire lock\nRedis SET NX EX\nor threading.Lock() fallback"]
        WORK["Execute critical section"]
        RELEASE["Release lock\nDEL key"]
    end

    PIPELINE_RUN --> IDEMP
    PROFILE_UPDATE --> DLOCK
```

---

## 12. Security & Auth Architecture

```mermaid
graph TD
    subgraph AUTH_FLOW["Authentication Flow"]
        EMAIL["User: Email + Password\nor Magic Link OTP"]
        SUPA_AUTH["Supabase Auth\n(email/OTP provider)"]
        JWT["JWT issued\n(ES256 algorithm\nHS256 fallback)"]
        FRONTEND_STORE["Frontend stores JWT\nin React state / memory"]

        EMAIL --> SUPA_AUTH
        SUPA_AUTH --> JWT
        JWT --> FRONTEND_STORE
    end

    subgraph BACKEND_VERIFY["Backend JWT Verification"]
        HEADER["Authorization: Bearer TOKEN"]
        DECODE["PyJWT decode\nES256 → HS256 fallback"]
        CLAIM["Extract: sub=user_id, email"]
        AUTH_USER["AuthUser object\ninjected via Depends()"]

        HEADER --> DECODE
        DECODE --> CLAIM
        CLAIM --> AUTH_USER
    end

    subgraph MULTITENANT["Multi-Tenant Isolation"]
        RLS2["Supabase RLS\nauth.uid() = user_id\nAll queries row-filtered"]
        ADMIN["Admin Client\nSERVICE_KEY bypasses RLS\nBackend-only, never sent to client"]
        ANON["Anon Client\nFrontend direct queries\nRLS enforced"]
    end

    FRONTEND_STORE --> HEADER
    AUTH_USER --> RLS2
```

### Security Headers Applied

```mermaid
graph LR
    RESP[Every HTTP Response] --> SH["SecurityHeadersMiddleware adds:"]
    SH --> H1["X-Content-Type-Options: nosniff"]
    SH --> H2["X-Frame-Options: DENY"]
    SH --> H3["X-XSS-Protection: 1; mode=block"]
    SH --> H4["Content-Security-Policy: default-src 'self'"]
    SH --> H5["Strict-Transport-Security: max-age=31536000"]
    SH --> H6["Referrer-Policy: strict-origin-when-cross-origin"]
```

---

## 13. Observability & Monitoring

```mermaid
graph LR
    subgraph OBS["Observability Stack"]
        STRUCT["Structured Logger\nJSON log lines\nrequest_id correlation"]
        METRICS["Prometheus Metrics\n/metrics endpoint\nRequest counts, latencies"]
        TELEMETRY["OpenTelemetry\nPhoenix collector integration\n(optional — env-gated)"]
        COST["Cost Tracker\nPer-agent token accounting\nLLM spend attribution"]
        LLM_TRACK["LLM Usage Tracker\nmodel, tokens, latency\nper-request logging"]
        CIRCUIT["Circuit Breaker Events\nState transitions logged\nHealth metrics emitted"]
        EVENTS["Event Bus\nasync pub/sub\nsystem:startup, agent:*, task:*"]
    end

    subgraph HEALTH["Health Check Endpoints"]
        READY["/api/ready\nService availability check"]
        HEALTH2["/api/v1/analytics/health\nsupabase + redis status"]
        CREDITS["/api/v1/analytics/credits\nQuery/token remaining"]
    end

    OBS --> HEALTH
```

### Cost Tracking Flow

```mermaid
sequenceDiagram
    participant Agent
    participant CostTracker
    participant CreditBudget
    participant CreditMiddleware
    participant Client

    Agent->>CostTracker: record_usage(model, tokens, cost)
    CostTracker->>CostTracker: Accumulate per-user daily spend
    CostTracker-->>Agent: usage logged

    CreditBudget->>CreditBudget: Decrement query_remaining
    CreditBudget->>CreditBudget: Decrement token_remaining

    CreditMiddleware->>CreditMiddleware: Read credit headers post-request
    CreditMiddleware-->>Client: X-Credits-Queries-Remaining: N
    CreditMiddleware-->>Client: X-Credits-Tokens-Remaining: N

    Client->>Client: Update credit display\nin Topbar
```

---

## 14. User Journey Flows

### New User Onboarding

```mermaid
journey
    title New User Onboarding Journey
    section Registration
      Visit app           : 5: User
      Click Sign Up       : 5: User
      Enter email         : 4: User
      Receive OTP / set password : 3: User, Supabase
      JWT issued          : 5: Supabase
    section Profile Setup
      Redirect to workspace      : 5: App
      See ProfileCompletionPanel : 4: App
      Enter name + location      : 4: User
      Enter professional summary : 3: User
      Submit → POST /profile     : 4: User, API
      Profile created in Supabase: 5: API
      has_profile = true         : 5: API
    section First Use
      Workspace unlocks          : 5: App
      See 13-panel sidebar       : 5: User
      Upload resume (RAG index)  : 3: User
      Run first job search       : 5: User
      View match scores          : 5: App
```

### Full Autonomous Pipeline Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant WS
    participant PipelineAPI
    participant Scout
    participant Analyst
    participant CompanyResearcher
    participant ResumeTailor
    participant CoverLetter
    participant Applier
    participant DB

    User->>Frontend: Set query + options\nClick "Start Pipeline"
    Frontend->>PipelineAPI: POST /api/v1/pipeline/run
    PipelineAPI->>WS: emit pipeline:start

    PipelineAPI->>Scout: ScoutAgent.run(query, location)
    Scout->>Scout: SerpAPI search → filter ATS URLs
    Scout-->>PipelineAPI: List[ScrapedJob] (8 jobs)
    PipelineAPI->>WS: emit scout:found {count: 8}

    loop For each job
        PipelineAPI->>Analyst: AnalystAgent.run(url, resume)
        Analyst->>Analyst: Fetch + parse JD
        Analyst->>Analyst: Groq LLM → JobAnalysis
        Analyst-->>PipelineAPI: match_score=82
        PipelineAPI->>WS: emit analyst:result {score: 82}

        alt match_score ≥ threshold AND use_company_research
            PipelineAPI->>CompanyResearcher: research(company)
            CompanyResearcher-->>PipelineAPI: CompanyDossier
            PipelineAPI->>WS: emit company:result
        end

        alt use_resume_tailoring
            PipelineAPI->>ResumeTailor: tailor(jd, profile)
            ResumeTailor-->>PipelineAPI: LaTeX resume
            PipelineAPI->>WS: emit resume:generated
        end

        alt use_cover_letter
            PipelineAPI->>CoverLetter: generate(jd, company, profile)
            CoverLetter-->>PipelineAPI: Cover letter text
            PipelineAPI->>WS: emit cover_letter:complete
        end

        alt auto_apply=true
            PipelineAPI->>Applier: apply(url, profile, resume_pdf)
            Applier->>WS: stream screenshots (1/s)
            Applier->>WS: emit hitl:request (if needed)
            User->>WS: hitl:response (answer)
            Applier->>WS: emit draft:review (before submit)
            User->>WS: draft:confirm
            Applier-->>PipelineAPI: applied=true
            PipelineAPI->>DB: Save to discovered_jobs
            PipelineAPI->>WS: emit applier:complete
        end
    end

    PipelineAPI->>WS: emit pipeline:complete {applied:3, skipped:5}
    PipelineAPI->>DB: clear checkpoint
```

### Live Agent (Direct URL) Flow

```mermaid
flowchart TD
    USER([User pastes job URL]) --> LIVE_FORM[Fill URL in LiveAgentPanel\nToggle Draft Mode]
    LIVE_FORM --> POST_WS[POST /api/v1/pipeline/live-apply\n+ WS session_id]
    POST_WS --> LIVE_SVC[LiveApplierService\n init with user_id]
    LIVE_SVC --> LOAD_PROFILE[Load UserProfile from Supabase\nBuild YAML task file]
    LOAD_PROFILE --> BROWSER[browser-use: start Chrome\nProactorEventLoop on Windows]
    BROWSER --> NAVIGATE[Navigate to job URL]
    NAVIGATE --> FILL[Form fill loop\nUsing profile data]
    FILL --> SCREENSHOT[Screenshot every 1-2s\n→ WS broadcast]
    FILL --> HITL_CHECK{Need human input?}
    HITL_CHECK -- Yes --> HITL2[emit hitl:request\nBlock on asyncio.Future]
    HITL2 --> USER_REPLY[User types in chat]
    USER_REPLY --> RESOLVE2[Future resolved → agent continues]
    FILL --> DRAFT_CHECK{Draft mode on\n+ Submit button?}
    DRAFT_CHECK -- Yes --> DRAFT2[emit draft:review\nShow form preview]
    DRAFT2 --> USER_CONFIRM[User confirms / edits]
    USER_CONFIRM --> SUBMIT[Submit form]
    SUBMIT --> DONE([emit applier:complete])
```

---

## 15. Data Flow: Job Application Pipeline

```mermaid
flowchart LR
    subgraph INPUT["Input Layer"]
        USER_QUERY["user query\n'AI Engineer remote'"]
        USER_PROFILE["UserProfile JSONB\nfrom Supabase"]
        RESUME_PDF["Primary Resume PDF\nfrom Storage"]
    end

    subgraph DISCOVERY["Discovery Layer"]
        SERPAPI2["SerpAPI\nGoogle Jobs"]
        ATS_FILTER["ATS URL filter\nGreenhouse - Lever - Ashby"]
        SCRAPED["ScrapedJob list\nurl, title, company, status"]
    end

    subgraph ANALYSIS["Analysis Layer"]
        HTML_SCRAPE["BeautifulSoup\nJD text extraction"]
        GROQ_ANALYST["Groq LLaMA-3.3 70B\nJSON completion"]
        JOB_ANALYSIS["JobAnalysis\nmatch_score, skills, gaps"]
        THRESHOLD["Threshold Gate\nmin_match_score filter"]
    end

    subgraph ENRICHMENT["Enrichment Layer"]
        COMPANY_DOSSIER["CompanyAgent\nCulture + Risks + Tips"]
        TAILORED_RESUME["ResumeAgent\nATS-optimised LaTeX"]
        COVER["CoverLetterAgent\nPersonalised letter"]
    end

    subgraph APPLICATION["Application Layer"]
        BROWSER2["browser-use\nHeadless Chrome"]
        FORM_FILL["Form field population\nfrom UserProfile"]
        PDF_UPLOAD["Resume PDF upload\nBytes from Storage"]
        CONFIRM["Draft confirmation\nor auto-submit"]
    end

    subgraph PERSISTENCE["Persistence Layer"]
        DISC_JOBS["discovered_jobs\nSupabase table"]
        TRACKER2["tracker_applications\nStatus lifecycle"]
        CACHE2["Cache\nCompany + Profile TTL"]
    end

    INPUT --> DISCOVERY
    DISCOVERY --> ANALYSIS
    USER_PROFILE --> ANALYSIS
    ANALYSIS --> |"score ≥ threshold"| ENRICHMENT
    INPUT --> ENRICHMENT
    ENRICHMENT --> APPLICATION
    APPLICATION --> PERSISTENCE
    ANALYSIS --> PERSISTENCE
```

---

## 16. Inter-Agent Communication Protocol

```mermaid
graph TD
    subgraph PROTOCOL["AgentProtocol — Event-Bus-Backed Messaging"]
        BROADCAST2["broadcast(from, intent, payload)\nDelivers to all subscribed agents"]
        REQUEST2["request(from, to, task, payload)\nDirect request with timeout"]
        DELEGATE2["delegate(from, to, task, payload)\nFire-and-forget sub-task"]
    end

    subgraph INTENTS["MessageIntent Types"]
        INFORM["INFORM\nShare discovery\nno reply needed"]
        REQUEST3["REQUEST\nAsk for data\nawaits response"]
        DELEGATE3["DELEGATE\nHand off sub-task\nfire and forget"]
        FEEDBACK2["FEEDBACK\nQuality rating\npropagates to memory"]
    end

    subgraph EXAMPLE["Example: Cross-Agent Collaboration"]
        CLA2["CoverLetterAgent\nneeds company culture"] -->|"request(to='company_agent',\ntask='get_culture')"| CA2["CompanyAgent\nlookup + return dossier"]
        CA2 -->|"INFORM: red_flag found"| RA2["ResumeAgent\nadjust framing"]
        IA2["InterviewAgent\ngot insight"] -->|"INFORM: common question"| TA2["TrackerAgent\nlog for prep reminder"]
    end

    PROTOCOL --> INTENTS
```

### Message Schema

```mermaid
classDiagram
    class AgentMessage {
        +str from_agent
        +str to_agent
        +MessageIntent intent
        +Dict payload
        +Priority priority
        +str correlation_id
        +float timestamp
        +str reply_to
    }

    class MessageIntent {
        <<enumeration>>
        INFORM
        REQUEST
        DELEGATE
        FEEDBACK
    }

    class Priority {
        <<enumeration>>
        LOW
        NORMAL
        HIGH
        CRITICAL
    }

    AgentMessage --> MessageIntent
    AgentMessage --> Priority
```

---

## 17. Deployment Architecture

### Current Development Topology

```mermaid
graph TB
    subgraph LOCAL["Developer Machine (Windows)"]
        FE_DEV["Next.js Dev Server\nnpm run dev\nlocalhost:3000"]
        BE_DEV["FastAPI + Uvicorn\nuvicorn src.main:app\nlocalhost:8000\nProactorEventLoop"]
        VENV[".venv Python 3.11\npip install -r requirements.txt"]
        CHROME["Google Chrome\nfor browser-use\nauto-detected path"]
    end

    subgraph CLOUD["Cloud Services"]
        SUPA_CLOUD["Supabase Cloud\nPostgreSQL + Auth + Storage\n+ PostgREST API\n+ pgvector"]
        GROQ_API["Groq API\nllama-3.3-70b-versatile"]
        OR_API["OpenRouter API\nClaude-3 / GPT-4o"]
        GEMINI_API["Google Gemini API\ngemini-1.5-pro"]
        SERPAPI3["SerpAPI\nGoogle Jobs search"]
    end

    FE_DEV --> |"HTTP/WS\nlocalhost:8000"| BE_DEV
    BE_DEV --> SUPA_CLOUD
    BE_DEV --> GROQ_API
    BE_DEV --> OR_API
    BE_DEV --> GEMINI_API
    BE_DEV --> SERPAPI3
```

### Production-Ready Architecture (Target)

```mermaid
graph TB
    subgraph CDN["Edge / CDN"]
        VERCEL["Vercel / Cloudflare\nNext.js Static + SSR\nEdge caching"]
    end

    subgraph API_TIER["API Tier"]
        LB["Load Balancer\nnginx / AWS ALB"]
        API1["FastAPI instance 1\ngunicorn + uvicorn workers"]
        API2["FastAPI instance 2"]
    end

    subgraph WORKER_TIER["Background Workers"]
        CELERY["Celery Workers\nsrc/worker/\nLong-running pipeline jobs"]
        REDIS_Q["Redis Broker\nTask queue + results backend"]
    end

    subgraph DATA_TIER["Data Tier"]
        SUPA_PROD["Supabase\nProduction Project\nPostgreSQL + pgvector"]
        STORAGE["Supabase Storage\nResume PDFs, generated docs"]
        REDIS_CACHE["Redis Cache\nProfile cache, LLM cache"]
    end

    CDN --> LB
    LB --> API1
    LB --> API2
    API1 --> REDIS_Q
    API2 --> REDIS_Q
    REDIS_Q --> CELERY
    API1 --> DATA_TIER
    API2 --> DATA_TIER
    CELERY --> DATA_TIER
```

---

## Appendix: Technology Stack Reference

| Layer | Technology | Purpose |
|---|---|---|
| Frontend framework | Next.js 14 (App Router) | SSR + React client |
| Frontend state | useState / useCallback | Local component state |
| Frontend real-time | WebSocket (native) | Pipeline event streaming |
| Backend framework | FastAPI 0.111 | Async REST + WebSocket |
| Backend runtime | Python 3.11 (uvicorn) | ASGI server |
| AI orchestration | LangGraph | State machine pipeline |
| LLM primary | Groq (LLaMA-3.3 70B) | Fast inference |
| LLM fallback 1 | OpenRouter | Claude-3 / GPT-4o |
| LLM fallback 2 | Google Gemini | Long context |
| LLM embeddings | OpenAI text-embedding-3-small | RAG index |
| Browser automation | browser-use | Chrome form filling |
| Web scraping | BeautifulSoup4 + requests | JD extraction |
| Job search | SerpAPI | Google Jobs results |
| Database | Supabase PostgreSQL | Primary data store |
| Vector search | pgvector | RAG similarity search |
| Auth | Supabase Auth | JWT ES256 |
| File storage | Supabase Storage | Resume PDFs |
| Cache | Redis (optional) / in-memory | TTL cache |
| Task queue | Celery + Redis | Async background jobs |
| Validation | Pydantic v2 | Request/response schemas |
| Config | pydantic-settings | Env var management |
| Observability | Prometheus + OpenTelemetry | Metrics + traces |
| PDF generation | pdflatex / reportlab | Resume PDFs |
| ORM | Supabase Python client | Admin + user queries |
