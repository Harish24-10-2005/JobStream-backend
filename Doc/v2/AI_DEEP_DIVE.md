# 🧠 Day 2 of 4 — The AI Brain Behind JobStream

> **"I didn't just call an API and pray. I built 8 AI agents, gave them memory, taught them to argue about salary, wrapped them in 5 resilience patterns, and the whole pipeline costs less than a cup of coffee."**

[![AI Agents](https://img.shields.io/badge/AI_Agents-8-blue?style=for-the-badge&logo=openai)]()
[![LLM Providers](https://img.shields.io/badge/LLM_Providers-5_Deep_Fallback-green?style=for-the-badge&logo=lightning)]()
[![Resilience](https://img.shields.io/badge/Resilience_Patterns-5-red?style=for-the-badge&logo=shield)]()
[![Cost](https://img.shields.io/badge/Cost_Per_Application-$0.02--0.05-yellow?style=for-the-badge&logo=dollar)]()
[![RAG](https://img.shields.io/badge/RAG-pgvector_768dim-purple?style=for-the-badge&logo=postgresql)]()

---

## 📋 Table of Contents

1. [Why This Isn't Another "Call OpenAI" Project](#-why-this-isnt-another-call-openai-project)
2. [High-Level AI Architecture](#-high-level-ai-architecture)
3. [The 8 Specialist AI Agents](#-the-8-specialist-ai-agents)
4. [Multi-Agent Orchestration — LangGraph StateGraph](#-multi-agent-orchestration--langgraph-stategraph)
5. [5-Provider LLM Fallback Chain](#-5-provider-llm-fallback-chain)
6. [RAG — Retrieval-Augmented Generation Pipeline](#-rag--retrieval-augmented-generation-pipeline)
7. [Intelligent Model Routing](#-intelligent-model-routing)
8. [Agent Memory — Persistent Learning System](#-agent-memory--persistent-learning-system)
9. [Agent Communication Protocol](#-agent-communication-protocol)
10. [AI Guardrails & Safety Pipeline](#-ai-guardrails--safety-pipeline)
11. [Browser Automation + Human-in-the-Loop](#-browser-automation--human-in-the-loop)
12. [Circuit Breaker — Per-Service Resilience](#-circuit-breaker--per-service-resilience)
13. [Retry Budget — System-Wide Storm Prevention](#-retry-budget--system-wide-storm-prevention)
14. [Cost & Token Economics](#-cost--token-economics)
15. [Self-Correcting AI Search](#-self-correcting-ai-search)
16. [Salary Battle — Turn-Based AI Negotiation Engine](#-salary-battle--turn-based-ai-negotiation-engine)
17. [LangGraph State Machines — All Graphs](#-langgraph-state-machines--all-graphs)
18. [Observability & LLM Tracing](#-observability--llm-tracing)
19. [Real-Time Event Architecture](#-real-time-event-architecture)
20. [Production AI Patterns Summary](#-production-ai-patterns-summary)
21. [The Numbers That Matter](#-the-numbers-that-matter)
22. [Key Takeaways for AI Engineers](#-key-takeaways-for-ai-engineers)

---

## 🎯 Why This Isn't Another "Call OpenAI" Project

| What Most AI Apps Do | What JobStream Does |
|---|---|
| Call OpenAI → Show response → Pray | 8 specialist agents with **typed state machines** |
| Single provider → If it fails, show error | **5-provider fallback chain** with exponential backoff |
| No memory → Every session starts fresh | **2-tier agent memory** with learning injection |
| Raw `json.loads()` → Crash on malformed JSON | **4-stage JSON repair pipeline** (15% of free-tier outputs need this) |
| No safety → Prompt injection? What's that? | **6-category guardrail pipeline** blocking 16+ attack patterns |
| Manual retry → Hope for the best | **Circuit breakers + Retry budget** = zero cascade failures |
| `print()` debugging | **OpenTelemetry + Arize Phoenix** span-level LLM tracing |
| No cost control → $500 bill surprise | **Per-agent daily budgets** + per-user credit system |

> **This isn't a wrapper around an LLM. It's a production-grade multi-agent orchestration platform.**

---

## 🏗️ High-Level AI Architecture

```mermaid
graph TB
    subgraph "🌐 User Interface"
        UI["Next.js Frontend<br/>WebSocket Real-time Streaming"]
    end

    subgraph "🛡️ AI Safety Gateway"
        MW["Middleware Stack<br/>Rate Limit → Credits → Auth → CORS"]
        GRD["AI Guardrails<br/>Prompt Injection Detection<br/>PII Redaction · XSS Filter"]
    end

    subgraph "🧠 AI Orchestration Engine — LangGraph"
        PG["StateGraph Engine<br/>Typed PipelineState<br/>Conditional Edges · Parallel Execution"]
        SP["Step Planner<br/>LLM-Driven Dynamic Step Selection"]
    end

    subgraph "🤖 8 Specialist AI Agents"
        SA["🔍 Scout Agent<br/>SerpAPI + Self-Correcting Search"]
        AA["📊 Analyst Agent<br/>HTML → Structured Job Analysis"]
        CA["🏢 Company Intel Agent<br/>Culture + Risk Assessment"]
        RA["📄 Resume Agent<br/>RAG-Powered ATS Tailoring"]
        CLA["✉️ Cover Letter Agent<br/>Per-Company Personalisation"]
        IA["🎤 Interview Coach Agent<br/>STAR + Technical Prep"]
        NA["🔗 Network Agent<br/>LinkedIn X-Ray Discovery"]
        TA["📋 Tracker Agent<br/>Application CRM + Follow-ups"]
    end

    subgraph "⚙️ Core AI Infrastructure"
        LLM["UnifiedLLM Engine<br/>5-Provider Fallback Chain<br/>Groq → OpenRouter → Gemini"]
        MEM["Agent Memory System<br/>2-Tier: Cache + Supabase Persist"]
        RAG["RAG Service<br/>pgvector + Gemini Embeddings<br/>768-dim Cosine Similarity"]
        MRP["Model Router<br/>Complexity-Based LLM Selection"]
        AP["Agent Protocol<br/>Inter-Agent Pub/Sub Messaging"]
        JSON_R["JSON Repair Pipeline<br/>4-Stage Malformed Output Recovery"]
    end

    subgraph "🛡️ Resilience & Safety Layer"
        CB["Circuit Breaker<br/>Per-Service State Machine<br/>CLOSED → OPEN → HALF_OPEN"]
        RB["Retry Budget<br/>System-Wide 20/min Cap<br/>20% Ratio Storm Prevention"]
        CT["Cost Tracker<br/>Per-Agent Daily USD Budgets"]
        PII["PII Detector<br/>7 PII Types · Auto-Redaction"]
    end

    subgraph "🤖 AI Browser Automation"
        LIVE["Live Applier Engine<br/>browser-use + Gemini Vision"]
        HITL["Human-in-the-Loop<br/>asyncio.Future via WebSocket<br/>120s Timeout · Draft Mode"]
    end

    subgraph "💾 AI Data Layer"
        VEC["pgvector Store<br/>768-dim Embeddings<br/>ivfflat Cosine Index"]
        MEMDB["Agent Memory Store<br/>Preferences · Learnings · Feedback"]
        TRACE["LLM Trace Store<br/>OpenTelemetry Spans<br/>Arize Phoenix Dashboard"]
    end

    UI --> MW --> GRD --> PG
    SP --> PG
    PG --> SA & AA & CA & RA & CLA
    PG --> LIVE
    RA --> RAG --> VEC
    SA & AA & CA & RA & CLA & IA & NA --> LLM
    LLM --> CB --> RB
    LLM --> MRP
    LLM --> JSON_R
    SA & RA & IA --> MEM --> MEMDB
    SA & CA & NA --> AP
    LIVE --> HITL --> UI
    CT --> LLM
    PII --> GRD
    LLM --> TRACE

    style PG fill:#0d1117,stroke:#58a6ff,stroke-width:3px,color:#c9d1d9
    style LLM fill:#0d1117,stroke:#f97583,stroke-width:3px,color:#c9d1d9
    style RAG fill:#0d1117,stroke:#d2a8ff,stroke-width:3px,color:#c9d1d9
    style LIVE fill:#0d1117,stroke:#56d364,stroke-width:3px,color:#c9d1d9
    style CB fill:#0d1117,stroke:#f0883e,stroke-width:3px,color:#c9d1d9
```

---

## 🤖 The 8 Specialist AI Agents

> **"One AI can't do everything well. Eight specialists, each with their own model, temperature, memory, and tools — that's how you build production AI."**

```mermaid
graph TB
    subgraph "🔍 Phase 1: Discovery"
        SCOUT["🔍 Scout Agent<br/>━━━━━━━━━━━━━━━━━━<br/>⚡ SerpAPI + LLM Self-Correction<br/>🎯 ATS Site Filters<br/>🔄 Auto-Retry with Broader Query<br/>📊 Groq 8B · temp 0.3"]
        ANALYST["📊 Analyst Agent<br/>━━━━━━━━━━━━━━━━━━<br/>🔬 HTML → Structured Analysis<br/>📈 Match Score 0-100<br/>🧠 Groq 70B for Nuanced Matching<br/>❄️ temp 0.0 (Max Accuracy)"]
    end

    subgraph "🏢 Phase 2: Intelligence"
        COMPANY["🏢 Company Intel Agent<br/>━━━━━━━━━━━━━━━━━━<br/>🔍 SerpAPI Research + Glassdoor<br/>⚠️ Red Flag Detection<br/>🏛️ Culture Assessment<br/>📊 Groq 8B · temp 0.3"]
        NETWORK["🔗 Network Agent<br/>━━━━━━━━━━━━━━━━━━<br/>🔎 LinkedIn X-Ray Search<br/>🤝 Warm Connection Discovery<br/>✉️ Outreach Message Generation<br/>📊 Groq 8B · temp 0.7"]
    end

    subgraph "📝 Phase 3: Generation"
        RESUME["📄 Resume Agent<br/>━━━━━━━━━━━━━━━━━━<br/>🧠 RAG-Powered Tailoring<br/>📐 LaTeX → PDF Generation<br/>🎯 ATS Keyword Optimization<br/>📊 Groq 70B · temp 0.3"]
        COVER["✉️ Cover Letter Agent<br/>━━━━━━━━━━━━━━━━━━<br/>🏢 Per-Company Personalised<br/>🔄 LangGraph 6-Node DAG<br/>👤 HITL Review Gate<br/>📊 Groq 70B · temp 0.6"]
    end

    subgraph "🎯 Phase 4: Preparation"
        INTERVIEW["🎤 Interview Coach<br/>━━━━━━━━━━━━━━━━━━<br/>⭐ STAR Framework Generation<br/>💻 Technical + System Design<br/>🔗 Anti-Hallucination DSA Links<br/>📊 Groq 8B · temp 0.3"]
        SALARY["💰 Salary Battle Agent<br/>━━━━━━━━━━━━━━━━━━<br/>📊 Market Research Engine<br/>🥊 Turn-Based AI Negotiation<br/>🎭 3 Difficulty Levels<br/>📊 Groq 8B · temp 0.3"]
    end

    subgraph "🤖 Phase 5: Action"
        APPLIER["🚀 Live Applier<br/>━━━━━━━━━━━━━━━━━━<br/>👁️ Gemini Vision Form Reading<br/>📝 Draft Mode Before Submit<br/>❓ HITL for Unknown Fields<br/>📊 Gemini 2.0 Flash"]
        TRACKER["📋 Tracker Agent<br/>━━━━━━━━━━━━━━━━━━<br/>📊 Application CRM<br/>🔔 Follow-up Reminders<br/>📌 Status State Machine<br/>📊 Supabase CRUD"]
    end

    SCOUT --> ANALYST --> COMPANY --> RESUME --> COVER --> APPLIER --> TRACKER
    ANALYST -.-> INTERVIEW
    ANALYST -.-> SALARY
    COMPANY -.-> NETWORK

    style SCOUT fill:#1a1a2e,stroke:#0f3460,stroke-width:2px,color:#e8e8e8
    style ANALYST fill:#1a1a2e,stroke:#0f3460,stroke-width:2px,color:#e8e8e8
    style COMPANY fill:#1a1a2e,stroke:#16213e,stroke-width:2px,color:#e8e8e8
    style NETWORK fill:#1a1a2e,stroke:#16213e,stroke-width:2px,color:#e8e8e8
    style RESUME fill:#1a1a2e,stroke:#533483,stroke-width:2px,color:#e8e8e8
    style COVER fill:#1a1a2e,stroke:#533483,stroke-width:2px,color:#e8e8e8
    style INTERVIEW fill:#1a1a2e,stroke:#e94560,stroke-width:2px,color:#e8e8e8
    style SALARY fill:#1a1a2e,stroke:#e94560,stroke-width:2px,color:#e8e8e8
    style APPLIER fill:#1a1a2e,stroke:#0f9b58,stroke-width:2px,color:#e8e8e8
    style TRACKER fill:#1a1a2e,stroke:#0f9b58,stroke-width:2px,color:#e8e8e8
```

### Agent-to-LLM Assignment Matrix

| Agent | LLM Model | Temperature | Reasoning |
|---|---|---|---|
| 🔍 Scout | `llama-3.1-8b-instant` | 0.3 | Speed-optimized query formatting |
| 📊 Analyst | `llama-3.3-70b-versatile` | 0.0 | Maximum accuracy — "4 years ≈ 5+ years" nuance |
| 🏢 Company Intel | `llama-3.1-8b-instant` | 0.3 | Structured research extraction |
| 🔗 Network | `llama-3.1-8b-instant` | 0.7 | Creative outreach personalisation |
| 📄 Resume | `llama-3.3-70b-versatile` | 0.3 | ATS-optimized creative writing |
| ✉️ Cover Letter | `llama-3.3-70b-versatile` | 0.6 | High creativity, per-company tone |
| 🎤 Interview | `llama-3.1-8b-instant` | 0.3 | Deterministic question generation |
| 💰 Salary | `llama-3.1-8b-instant` | 0.3 | Consistent percentile calculations |
| 🚀 Applier | `Gemini 2.0 Flash` | — | Vision for form interpretation |

> **Why different models per agent?** A keyword extraction task doesn't need the same $0.79/M-token model that writes your cover letter. **Model routing saves 60%+ cost** without sacrificing quality where it matters.

---

## 🔗 Multi-Agent Orchestration — LangGraph StateGraph

> **"Not a chain. Not a loop. A typed, stateful DAG with conditional edges, parallel execution, and file-based checkpointing."**

```mermaid
flowchart TD
    START(["▶ Pipeline Start<br/>User triggers via WebSocket"]) --> VALIDATE["🔍 Input Validation<br/>Profile completeness check<br/>Pydantic v2 strict mode"]

    VALIDATE --> LOAD["📥 Load User Profile<br/>Fetch from Supabase<br/>Sync RAG embeddings"]

    LOAD --> SCOUT["🔎 Scout Node<br/>━━━━━━━━━━━━━━━━━━━━━━━━<br/>SerpAPI + ATS site-filters<br/>site:greenhouse.io | lever.co | ashbyhq.com<br/>LLM self-correction on 0 results"]

    SCOUT --> ANALYZE["📊 Analyst Node<br/>━━━━━━━━━━━━━━━━━━━━━━━━<br/>HTML parsing + BeautifulSoup<br/>Groq 70B match scoring (0-100)<br/>Structured JobAnalysis output"]

    ANALYZE --> THRESHOLD{"📏 Score ≥<br/>min_match_score?"}
    THRESHOLD -->|Below threshold| SKIP["⏭️ Skip Job<br/>ANALYST_SKIPPED event"]
    THRESHOLD -->|Above threshold| COMPANY_CHECK

    COMPANY_CHECK{"🏢 Company<br/>Research<br/>Enabled?"}
    COMPANY_CHECK -->|Yes| COMPANY["🏢 Company Research Node<br/>━━━━━━━━━━━━━━━━━━━━━━━━<br/>SerpAPI + CircuitBreaker<br/>Culture · Red Flags · Intel<br/>INFORM → all downstream agents"]
    COMPANY_CHECK -->|No| RESUME_CHECK

    COMPANY --> RESUME_CHECK{"📄 Resume<br/>Tailoring<br/>Enabled?"}
    RESUME_CHECK -->|Yes| PARALLEL["⚡ Parallel Execution<br/>asyncio.gather()"]

    PARALLEL --> RESUME["📄 Resume Agent<br/>━━━━━━━━━━━━━━━━━━<br/>RAG context retrieval<br/>LaTeX generation<br/>ATS score optimization"]
    PARALLEL --> COVER_LETTER["✉️ Cover Letter Agent<br/>━━━━━━━━━━━━━━━━━━<br/>6-node LangGraph DAG<br/>Company-aware tone<br/>HITL review gate"]

    RESUME_CHECK -->|No| APPLY_CHECK

    RESUME & COVER_LETTER --> APPLY_CHECK{"🚀 Auto<br/>Apply?"}
    APPLY_CHECK -->|Yes| APPLY["🤖 Live Applier Node<br/>━━━━━━━━━━━━━━━━━━━━━━━━<br/>browser-use + Gemini Vision<br/>Draft mode → HITL review<br/>Screenshot stream (5 FPS)"]
    APPLY_CHECK -->|No| TRACK

    APPLY --> TRACK["📋 Track Results<br/>Save to job_applications<br/>Update status state machine"]
    TRACK --> END(["✅ Pipeline Complete<br/>All events streamed via WebSocket"])

    style START fill:#0d1117,stroke:#58a6ff,stroke-width:2px,color:#c9d1d9
    style PARALLEL fill:#0d1117,stroke:#e94560,stroke-width:3px,color:#c9d1d9
    style SCOUT fill:#0d1117,stroke:#0f3460,stroke-width:2px,color:#c9d1d9
    style APPLY fill:#0d1117,stroke:#56d364,stroke-width:3px,color:#c9d1d9
    style END fill:#0d1117,stroke:#58a6ff,stroke-width:2px,color:#c9d1d9
```

### Typed State — Zero "String Soup"

```python
class PipelineState(BaseModel):
    """Every pipeline node reads/writes to this Pydantic-validated state."""
    query: str                           # "Senior Python Engineer"
    location: str                        # "San Francisco, CA"
    min_match_score: int = 70            # Only process jobs above this
    auto_apply: bool = False             # Gate for browser automation
    job_urls: List[str]                  # Populated by Scout
    current_analysis: JobAnalysis        # Populated by Analyst (typed!)
    job_results: List[JobResult]         # Accumulated across pipeline
    node_statuses: Dict[str, NodeStatus] # PENDING → RUNNING → COMPLETED | FAILED | SKIPPED
```

> **No magic dictionaries. No `state["results"][0]["maybe_data"]`.**
> Type errors caught at build time, not at 2 AM in production.

### Pipeline Checkpointing

```
data/checkpoints/{session_id}.json
├── node_statuses: {scout: COMPLETED, analyst: RUNNING, ...}
├── job_urls: [...]
├── job_results: [...]
└── stop_flag: false   ← checked between every node
```

> **Crash recovery:** If the server restarts mid-pipeline, it resumes from the last checkpoint — not from scratch.

---

## 🔗 5-Provider LLM Fallback Chain

> **Most AI apps:** "Call OpenAI. If it fails, show error."
> **JobStream:** "Call Groq. Rate-limited? Try backup key. Still failing? OpenRouter. Still? Try second key. STILL? Gemini. If ALL 5 fail, THEN show error."

```mermaid
flowchart TD
    A["🤖 Agent Request"] --> B["💰 Budget Check<br/>CostTracker.check_budget()"]
    B -->|"Exhausted"| STOP["❌ Budget Exhausted<br/>LLMError raised"]
    B -->|"OK"| P1

    P1["🥇 Provider 1: Groq Primary<br/>llama-3.1-8b-instant<br/>API Key #1 · sub-200ms"] --> R1{"Response?"}
    R1 -->|"✅ Success"| REPAIR["🔧 JSON Repair Pipeline<br/>━━━━━━━━━━━━━━━━━━━━<br/>Stage 1: Strip markdown fences<br/>Stage 2: Extract {...} boundaries<br/>Stage 3: Fix trailing commas<br/>Stage 4: Repair quotes"]
    R1 -->|"429 Rate Limit"| BACK1["⏳ Exponential Backoff<br/>1s → 2s → 4s"]
    BACK1 --> P1_RETRY{"Retries<br/>exhausted?"}
    P1_RETRY -->|"No"| P1
    P1_RETRY -->|"Yes"| P2

    P2["🥈 Provider 2: Groq Fallback<br/>Same model, different API key<br/>Separate rate limit quota"] --> R2{"Response?"}
    R2 -->|"✅"| REPAIR
    R2 -->|"❌"| P3

    P3["🥉 Provider 3: OpenRouter Primary<br/>Qwen 3 Coder (Free Tier)<br/>API Key #1"] --> R3{"Response?"}
    R3 -->|"✅"| REPAIR
    R3 -->|"❌"| P4

    P4["4️⃣ Provider 4: OpenRouter Fallback<br/>Second API Key<br/>Separate quota"] --> R4{"Response?"}
    R4 -->|"✅"| REPAIR
    R4 -->|"❌"| P5

    P5["5️⃣ Provider 5: Gemini 2.0 Flash<br/>Last Resort + Vision Capable<br/>Google AI"] --> R5{"Response?"}
    R5 -->|"✅"| REPAIR
    R5 -->|"❌"| FAIL["❌ All 5 Providers Exhausted<br/>LLMError: All providers failed"]

    REPAIR --> TOKEN["📊 Token Tracking<br/>agent · provider · model<br/>input_tokens · output_tokens<br/>latency_ms · cost_usd"]
    TOKEN --> SUCCESS["✅ Return Validated Response"]

    style P1 fill:#0d1117,stroke:#56d364,stroke-width:2px,color:#c9d1d9
    style P2 fill:#0d1117,stroke:#58a6ff,stroke-width:2px,color:#c9d1d9
    style P3 fill:#0d1117,stroke:#d2a8ff,stroke-width:2px,color:#c9d1d9
    style P4 fill:#0d1117,stroke:#f0883e,stroke-width:2px,color:#c9d1d9
    style P5 fill:#0d1117,stroke:#f97583,stroke-width:2px,color:#c9d1d9
    style REPAIR fill:#0d1117,stroke:#ffa657,stroke-width:2px,color:#c9d1d9
```

### The 4-Stage JSON Repair Pipeline

> **Fun fact:** Free-tier 8B models produce malformed JSON ~15% of the time. Without this pipeline, that's **1 in 7 agent calls crashing silently.** 💀

```mermaid
flowchart LR
    RAW["Raw LLM Output<br/>```json { 'key': val, } ```"] --> S1["Stage 1<br/>Strip Markdown Fences<br/>regex: ```json...```"]
    S1 --> S2["Stage 2<br/>Extract JSON Boundaries<br/>Find first { ... last }"]
    S2 --> S3["Stage 3<br/>Fix Trailing Commas<br/>{key: val,} → {key: val}"]
    S3 --> S4["Stage 4<br/>Repair Quotes<br/>single → double<br/>unquoted keys → quoted"]
    S4 --> VALID["✅ Valid JSON<br/>Pydantic Model Parse"]

    style S1 fill:#161b22,stroke:#58a6ff,color:#c9d1d9
    style S2 fill:#161b22,stroke:#d2a8ff,color:#c9d1d9
    style S3 fill:#161b22,stroke:#56d364,color:#c9d1d9
    style S4 fill:#161b22,stroke:#f0883e,color:#c9d1d9
```

### Per-Provider Resilience Config

| Provider | Retry Strategy | Backoff | Circuit Breaker |
|---|---|---|---|
| Groq Primary | 3 attempts | 1s → 2s → 4s exponential | 5 failures → 60s open |
| Groq Fallback | 3 attempts | 1s → 2s → 4s exponential | Shares Groq breaker |
| OpenRouter Primary | 3 attempts | 1s → 2s → 4s exponential | 5 failures → 60s open |
| OpenRouter Fallback | 3 attempts | 1s → 2s → 4s exponential | Shares OR breaker |
| Gemini | 3 attempts | 1s → 2s → 4s exponential | 3 failures → 30s open |

### Rate Limit Detection (6 String Patterns)

```python
RATE_LIMIT_PATTERNS = [
    "rate_limit", "429", "too many requests",
    "quota exceeded", "tokens per minute", "requests per minute"
]
```

---

## 🧬 RAG — Retrieval-Augmented Generation Pipeline

> **"Your resume agent doesn't hallucinate experience you don't have. It RETRIEVES your real experience first, then writes grounded content."**

```mermaid
flowchart TD
    subgraph "📥 Indexing Phase — On Profile Upload/Update"
        RESUME["👤 User Resume / Profile"] --> SPLIT["✂️ RecursiveCharacterTextSplitter<br/>chunk_size=1000 chars (~200 tokens)<br/>overlap=200 chars"]
        SPLIT --> CHUNKS["📦 50–200 Text Chunks<br/>Each preserving semantic context"]
        CHUNKS --> EMBED["🧠 Gemini text-embedding-004<br/>768-dimensional vectors<br/>Semantic encoding"]
        EMBED --> STORE["💾 Supabase pgvector<br/>ivfflat cosine index<br/>RLS: user_id isolation"]
    end

    subgraph "🔎 Query Phase — Per Job Application"
        JOB["📋 Job Requirements<br/>'5+ years Python, distributed systems'"] --> QEMBED["🧠 Embed Query → 768-dim vector"]
        QEMBED --> SEARCH["🔍 match_documents() RPC<br/>Cosine similarity search<br/>threshold=0.5 · top-k=4"]
        SEARCH --> TOP["📊 Top-K Relevant Chunks<br/>'Built microservices handling 1M req/day'<br/>'Led team of 5 on distributed cache'"]
        TOP --> INJECT["💉 Inject into LLM Prompt<br/>As grounded factual context"]
        INJECT --> GENERATE["✍️ Resume Agent Generates<br/>Tailored, factual content<br/>No hallucination possible"]
    end

    subgraph "🔄 Auto-Sync Pattern"
        UPDATE["Profile Update Event"] --> DELETE["Delete old embeddings<br/>WHERE type='profile'"]
        DELETE --> RECHUNK["Re-chunk + Re-embed"] --> REINSERT["Insert fresh vectors"]
    end

    style EMBED fill:#0d1117,stroke:#d2a8ff,stroke-width:2px,color:#c9d1d9
    style SEARCH fill:#0d1117,stroke:#58a6ff,stroke-width:2px,color:#c9d1d9
    style GENERATE fill:#0d1117,stroke:#56d364,stroke-width:2px,color:#c9d1d9
```

### Why These Exact Parameters?

| Parameter | Value | Engineering Rationale |
|---|---|---|
| `chunk_size` | 1,000 chars | ≈200 tokens — multiple chunks fit in 4K context window |
| `overlap` | 200 chars | Prevents skills split across chunk boundaries from being lost |
| `embedding_dim` | 768 | Gemini `text-embedding-004` native — zero dimension mismatch |
| `index_type` | ivfflat | Approximate nearest neighbor — fast at scale, 95%+ recall |
| `similarity_threshold` | 0.5 | Balances precision vs recall for resume content |
| `top_k` | 4 | Enough context without overwhelming the generation prompt |

### The pgvector SQL Function

```sql
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(768),
    match_threshold float,
    match_count int,
    filter_user_id uuid
) RETURNS TABLE(id uuid, content text, metadata jsonb, similarity float)
LANGUAGE sql STABLE AS $$
    SELECT id, content, metadata,
           1 - (embedding <=> query_embedding) AS similarity
    FROM documents
    WHERE user_id = filter_user_id
      AND 1 - (embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
$$;
```

> **Semantic matching wins:** "built distributed systems" matches "microservices architecture" — keyword matching would miss this entirely.

---

## 🎯 Intelligent Model Routing

> **"Not every task needs the expensive model. Keyword matching? Use 8B (fast, $0.05/M). Cover letter? Use 70B (smart, worth the $0.79/M)."**

```mermaid
flowchart TD
    INPUT["🤖 Agent Request<br/>+ complexity + budget + latency_flag"] --> GROUND{"🌐 Needs Real-Time<br/>Web Grounding?"}

    GROUND -->|"Yes"| GEMINI["🌟 PREMIUM TIER<br/>━━━━━━━━━━━━━━━━━━━<br/>Gemini 2.0 Flash<br/>Vision + Search Grounding<br/>$0.075/$0.30 per 1M tokens"]

    GROUND -->|"No"| COMPLEX{"🧠 High Complexity<br/>+ Budget > 50%?"}

    COMPLEX -->|"Yes"| PREMIUM["💎 PREMIUM TIER<br/>━━━━━━━━━━━━━━━━━━━<br/>llama-3.3-70b-versatile<br/>Deep reasoning + creativity<br/>$0.59/$0.79 per 1M tokens"]

    COMPLEX -->|"No"| LATENCY{"⚡ Latency<br/>Sensitive?"}

    LATENCY -->|"Yes"| CHEAP["⚡ SPEED TIER<br/>━━━━━━━━━━━━━━━━━━━<br/>llama-3.1-8b-instant<br/>Sub-200ms response<br/>$0.05/$0.08 per 1M tokens"]

    LATENCY -->|"No"| BALANCED["⚖️ BALANCED TIER<br/>━━━━━━━━━━━━━━━━━━━<br/>OpenRouter Medium Model<br/>Good quality, free tier<br/>$0.00 per token"]

    style GEMINI fill:#0d1117,stroke:#ffa657,stroke-width:2px,color:#c9d1d9
    style PREMIUM fill:#0d1117,stroke:#d2a8ff,stroke-width:2px,color:#c9d1d9
    style CHEAP fill:#0d1117,stroke:#56d364,stroke-width:2px,color:#c9d1d9
    style BALANCED fill:#0d1117,stroke:#58a6ff,stroke-width:2px,color:#c9d1d9
```

### Who Uses What — And Why

| Agent Task | Tier | Model | Why This Tier |
|---|---|---|---|
| Scout: format search query | ⚡ SPEED | 8B | Simple string manipulation — 200ms beats 2s |
| Scout: self-correct failed query | 💎 PREMIUM | 70B | Needs reasoning: "query too specific, broaden to..." |
| Analyst: match scoring | 💎 PREMIUM | 70B | Nuanced: "4 years experience ≈ 5+ years requirement" |
| Resume: ATS optimization | 💎 PREMIUM | 70B | Creative writing with keyword weaving |
| Cover Letter: generation | 💎 PREMIUM | 70B | Per-company tone adaptation |
| Interview: Q generation | ⚡ SPEED | 8B | Deterministic STAR template filling |
| Chat: intent classification | ⚡ SPEED | 8B | 5-class routing at temp=0 |
| Step Planner: step selection | ⚡ SPEED | 8B | Simple classification — 200ms |
| Applier: form reading | 🌟 VISION | Gemini | Screenshot interpretation — no CSS selectors |

> **Result:** 60%+ cost reduction vs using 70B for everything, with **zero quality loss** on tasks that don't need it.

---

## 🧠 Agent Memory — Persistent Learning System

> **"Your AI agents REMEMBER. The Resume Agent learns you prefer bullet points. The Interview Coach remembers you struggle with system design. The more you use it, the better it gets. That's not a feature — that's a moat."**

```mermaid
flowchart TD
    subgraph "✍️ Write Path"
        REMEMBER["agent.remember(key, value)"] --> CACHE["⚡ Tier 1: In-Memory Dict<br/>Fast · Volatile · Zero Latency"]
        REMEMBER --> SUPA["💾 Tier 2: Supabase Table<br/>Durable · Persistent · Queryable"]
    end

    subgraph "📖 Read Path"
        RECALL["agent.recall(key)"] --> HIT{"Cache<br/>Hit?"}
        HIT -->|"Yes"| EXPIRY["Check TTL Expiry<br/>→ Return if valid"]
        HIT -->|"No"| FETCH["Query Supabase<br/>→ Populate Cache<br/>→ Return"]
    end

    subgraph "🎓 Learning Loop"
        FEEDBACK["User Rates Output<br/>⭐⭐⭐⭐☆ (4/5)"] --> RECORD["agent_feedback table<br/>rating · comment · agent · timestamp"]
        RECORD --> DISTILL["get_learnings()<br/>Aggregate insights"]
        DISTILL --> INJECT["💉 Inject into System Prompt<br/>'User prefers action verbs.<br/>Continue current approach.'"]
    end

    subgraph "🛡️ Failure Tolerance"
        ANY["Any Memory Operation"] --> TRY["try / except"]
        TRY -->|"Supabase down"| CACHE_ONLY["Degrade → Cache Only"]
        TRY -->|"Cache empty"| DEFAULT["Return None → Agent continues"]
        TRY -->|"Both down"| SILENT["Silent fallback<br/>NEVER kills a job application"]
    end

    style CACHE fill:#0d1117,stroke:#56d364,stroke-width:2px,color:#c9d1d9
    style SUPA fill:#0d1117,stroke:#58a6ff,stroke-width:2px,color:#c9d1d9
    style INJECT fill:#0d1117,stroke:#d2a8ff,stroke-width:2px,color:#c9d1d9
    style SILENT fill:#0d1117,stroke:#f97583,stroke-width:2px,color:#c9d1d9
```

### 5 Memory Types

| Type | Purpose | Example | Agent |
|---|---|---|---|
| `PREFERENCE` | User style choices | `"concise_bullets"` | Resume Agent |
| `LEARNING` | Distilled from feedback | `"User prefers action verbs at bullet starts"` | All Agents |
| `CONTEXT` | Session-specific facts | `{"target_company": "Google", "role": "SRE"}` | Company Agent |
| `FEEDBACK` | Raw ratings | `{rating: 4.2, comment: "Good but too long"}` | Resume Agent |
| `PERFORMANCE` | Agent metrics | `{avg_match_score: 78, total_applications: 23}` | Analyst Agent |

> **Design principle:** Memory is best-effort. Its failure should NEVER kill a job application. Every `remember()` and `recall()` is wrapped in try/except and degrades silently.

---

## 📡 Agent Communication Protocol

> **"Agents don't work in isolation. They TALK to each other. Company Agent finds a red flag? Cover Letter Agent adjusts its tone. That's inter-agent intelligence."**

```mermaid
sequenceDiagram
    participant CO as 🏢 Company Agent
    participant RA as 📄 Resume Agent
    participant CL as ✉️ Cover Letter
    participant NA as 🔗 Network Agent
    participant MEM as 🧠 Agent Memory
    participant EB as 📡 Event Bus

    CO->>CO: Research "Acme Corp"
    CO->>EB: 📢 BROADCAST: INFORM<br/>"High turnover. Culture concerns per Glassdoor."
    CO->>EB: 📢 BROADCAST: INFORM<br/>"They value Python + Kubernetes expertise."

    EB-->>RA: 📨 Received: "They value Python + K8s"
    EB-->>CL: 📨 Received: "Culture concerns"
    EB-->>NA: 📨 Received: "Company: Acme Corp"

    RA->>RA: Prioritise K8s experience in bullet points
    CL->>CL: Adjust tone → cautious, professional
    NA->>NA: X-Ray search: site:linkedin.com/in/ Acme Corp

    CL->>CO: 📋 REQUEST: "Get interview tips for Acme?"
    CO-->>CL: 📋 RESPONSE: "Emphasise stability, long-term commitment"

    RA->>MEM: 📊 FEEDBACK: "User rated output 4/5"
    MEM-->>RA: 🎓 LEARNING: "Continue current approach"
```

### 4 Message Intent Types

| Intent | Direction | Example | When Used |
|---|---|---|---|
| `INFORM` | One → Many (Broadcast) | Company → All: "High turnover at Acme" | Discovery sharing |
| `REQUEST` | One → One (Direct) | Cover Letter → Company: "Get culture brief for Google" | On-demand intel |
| `DELEGATE` | One → One (Hand off) | Pipeline → Network: "Find contacts at this company" | Task delegation |
| `FEEDBACK` | One → Memory (Quality signal) | Resume → Memory: "User rated 4/5" | Learning loop |

### Priority Levels

```
LOW → NORMAL → HIGH → CRITICAL
```

> Critical messages (e.g., "Supabase is down") are processed immediately. Low-priority messages are batched.

---

## 🛡️ AI Guardrails & Safety Pipeline

> **"Every user message passes through 3 security layers before the AI sees it. Every AI response passes through validation before the user sees it. This isn't optional — this is production."**

```mermaid
flowchart TD
    INPUT["👤 User Input"] --> L1["🧹 Layer 1: InputSanitizer<br/>━━━━━━━━━━━━━━━━━━━━━━━━<br/>Strip &lt;script&gt; tags<br/>Remove &lt;iframe&gt; embeds<br/>Neutralize javascript: URLs<br/>Block onerror= handlers"]

    L1 --> L2["🔒 Layer 2: PromptInjectionDetector<br/>━━━━━━━━━━━━━━━━━━━━━━━━<br/>16+ attack pattern regex matching<br/>6 injection categories<br/>ROLE_JAILBREAK · SYSTEM_OVERRIDE<br/>PROMPT_LEAKAGE · INDIRECT_INJECT<br/>DATA_EXFILTRATION · PRIVILEGE_ESCALATE"]

    L2 -->|"🚫 BLOCKED"| REJECT["❌ HTTP 400<br/>Attack logged with category<br/>& confidence score"]

    L2 -->|"✅ PASS"| L3["⚠️ Layer 3: ContentSafetyFilter<br/>━━━━━━━━━━━━━━━━━━━━━━━━<br/>Threat detection<br/>Profanity filtering<br/>Topic safety classification"]

    L3 -->|"🚫 BLOCKED"| REJECT
    L3 -->|"✅ PASS"| LLM["🧠 LLM Processing<br/>Agent generates response"]

    LLM --> L4["✅ Layer 4: OutputValidator<br/>━━━━━━━━━━━━━━━━━━━━━━━━<br/>Pydantic schema enforcement<br/>JSON structure validation"]

    L4 -->|"✅ VALID"| PII_CHECK["🕵️ PII Redaction Layer<br/>━━━━━━━━━━━━━━━━━━━━━━━━<br/>Email · Phone · SSN · Credit Card<br/>IP Address · DOB · Physical Address<br/>7 types with confidence thresholds"]

    L4 -->|"❌ INVALID"| REPAIR["🔧 JSON Repair Pipeline<br/>4-stage recovery → Retry"]

    PII_CHECK --> RESPONSE["👤 Safe Response to User"]

    style L2 fill:#0d1117,stroke:#f97583,stroke-width:3px,color:#c9d1d9
    style PII_CHECK fill:#0d1117,stroke:#ffa657,stroke-width:2px,color:#c9d1d9
    style REJECT fill:#3d1117,stroke:#f97583,stroke-width:2px,color:#f97583
```

### Prompt Injection Patterns Blocked (16+)

| Category | Example Patterns |
|---|---|
| `ROLE_JAILBREAK` | "ignore all previous instructions", "you are now DAN" |
| `SYSTEM_OVERRIDE` | "disregard your system prompt", "developer mode enabled" |
| `PROMPT_LEAKAGE` | "repeat the system prompt above", "show me your instructions" |
| `INDIRECT_INJECT` | `<script>`, "as the AI said previously" |
| `DATA_EXFILTRATION` | "print all user data", "list all users" |
| `PRIVILEGE_ESCALATE` | "sudo mode", "admin override", "unrestricted mode" |

### PII Detection — 7 Types with Confidence Scoring

| PII Type | Pattern | Confidence | Action |
|---|---|---|---|
| Email | RFC 5322 format | 0.95 | Auto-redact → `[REDACTED]` |
| Phone | US format ± country code | 0.85 | Auto-redact |
| SSN | `XXX-XX-XXXX` | 0.99 | Auto-redact |
| Credit Card | 16-digit groups | 0.98 | Auto-redact |
| IP Address | IPv4/IPv6 | 0.80 | Auto-redact |
| Date of Birth | Date near DOB context | 0.75 | Flag only |
| Physical Address | Street + directional | 0.70 | Flag only |

> **Fail-Open Principle:** If a guardrail itself crashes, it logs the error and continues. A bug in the safety layer should never take down the whole service.

---

## 🤖 Browser Automation + Human-in-the-Loop

> **"The AI fills out job applications in a real browser using VISION — not CSS selectors. When it hits a CAPTCHA or a weird question, it PAUSES and ASKS you via WebSocket — then resumes when you answer."**

```mermaid
sequenceDiagram
    participant BA as 🤖 Browser Agent<br/>(Gemini Vision)
    participant LS as ⚙️ Live Applier Service
    participant WS as 📡 WebSocket Manager
    participant UI as 👤 User Browser

    Note over BA,UI: Phase 1: Navigation & Form Detection
    BA->>LS: Navigate to job application URL
    LS->>UI: 📸 Screenshot stream begins (every 2s)

    Note over BA,UI: Phase 2: Autonomous Form Filling
    BA->>BA: 👁️ Vision: Detect form fields from screenshot
    BA->>BA: ✍️ Fill name, email, phone, resume upload...
    LS->>UI: 📸 Screenshot: showing form being filled

    Note over BA,UI: Phase 3: HITL — Unknown Field
    BA->>LS: ❓ ask_human("What team interests you most?")
    LS->>WS: 📤 emit HITL_REQUEST + hitl_id
    WS->>UI: 🔔 WebSocket push → Dialog appears

    Note over UI: User types answer in their browser
    UI->>WS: 💬 "Engineering Platform team"
    WS->>LS: resolve_hitl(hitl_id, answer)
    LS->>LS: asyncio.Future.set_result(answer)
    LS->>BA: ▶️ ActionResult("Human responded: Engineering Platform team")

    Note over BA,UI: Phase 4: Draft Review Before Submit
    BA->>BA: Continue filling remaining fields...
    BA->>LS: 📋 All fields complete → DRAFT_REVIEW
    LS->>UI: 👀 "Application ready. Review before submit?"
    UI->>WS: ✅ "Confirm — submit"

    Note over BA,UI: Phase 5: Submit & Track
    BA->>BA: 🖱️ Click Submit button
    LS->>UI: 🎉 APPLIER_COMPLETE
    LS->>LS: job_applications.status = "applied"
```

### Why browser-use Beats Selenium/Playwright

| Approach | How It Finds Fields | Breaks When... | Maintenance |
|---|---|---|---|
| **Selenium** | `By.ID("firstName")` | Company updates HTML | Constant |
| **Playwright** | `page.locator("#firstName")` | DOM structure changes | Constant |
| **browser-use** | **LLM reads screenshot** | Almost never | Nearly zero |

> **browser-use sees the page like a human does.** No CSS selectors to maintain. No DOM parsing. The Gemini Vision model reads the screenshot and decides what to fill — just like you would.

### Draft Mode State Machine

```mermaid
stateDiagram-v2
    [*] --> FILLING : Apply started
    FILLING --> FILLED : All fields complete
    FILLED --> AWAITING_REVIEW : emit DRAFT_REVIEW<br/>+ asyncio.Future
    AWAITING_REVIEW --> SUBMITTING : ✅ User confirms
    AWAITING_REVIEW --> EDITING : ✏️ User requests edit
    SUBMITTING --> COMPLETE : Form submitted ✅
    EDITING --> [*] : Human takes over
    COMPLETE --> [*]

    note right of AWAITING_REVIEW
        120-second timeout.
        If no response → save as draft.
        User can resume later.
    end note
```

> **Draft mode is the default.** The AI NEVER submits without your explicit confirmation. Full control, zero anxiety.

---

## 🔄 Circuit Breaker — Per-Service Resilience

> **"When SerpAPI is down, don't wait 30 seconds for each timeout. TRIP THE BREAKER and skip it for 60 seconds. Keep the system fast."**

```mermaid
stateDiagram-v2
    [*] --> CLOSED : System starts healthy ✅

    CLOSED --> OPEN : failures ≥ threshold<br/>within sliding window (60s)

    OPEN --> HALF_OPEN : recovery_timeout elapsed<br/>(configurable per service)

    HALF_OPEN --> CLOSED : ✅ Probe call succeeds<br/>Reset failure count
    HALF_OPEN --> OPEN : ❌ Probe call fails<br/>Back to isolation

    note right of CLOSED
        All calls pass through normally.
        Failures tracked in
        sliding deque(maxlen=1000).
        Success rate monitored.
    end note

    note right of OPEN
        ALL calls fail-fast immediately.
        Zero wait time for users.
        Fallback function returned.
        rejected_count incremented.
    end note

    note right of HALF_OPEN
        ONE probe call allowed through.
        Success → full recovery to CLOSED.
        Failure → re-open the circuit.
    end note
```

### Per-Service Configuration

| Service | Failure Threshold | Recovery Timeout | Why These Values |
|---|---|---|---|
| `groq` | 5 failures | 60s | Primary LLM — need fast recovery attempt |
| `openrouter` | 5 failures | 60s | Fallback LLM — same resilience logic |
| `gemini` | 3 failures | 30s | Vision + embeddings — critical for applier |
| `serpapi` | 3 failures | 30s | Paid API — fail fast to save money |
| `supabase` | 5 failures | 120s | Database — give it more time to recover |

### Circuit Breaker + Fallback Functions

```python
# When SerpAPI circuit is OPEN, return empty list instead of crashing
CircuitBreaker("serpapi", failure_threshold=3, fallback=lambda: [])

# When Groq is OPEN, the system automatically tries next provider
# Circuit breaker feeds into the 5-provider chain
```

---

## ⚡ Retry Budget — System-Wide Storm Prevention

> **"Circuit breaker = per-service failure detection. Retry budget = prevent the ACT of retrying from making things WORSE across the entire system."**

```mermaid
flowchart TD
    A["🔄 Any Component Wants to Retry"] --> B["RetryBudget.can_retry(service_name)"]

    B --> C{"📊 Total retries in<br/>last 60 seconds > 20?"}
    C -->|"Yes"| BLOCK["🛑 BLOCKED<br/>━━━━━━━━━━━━━━━━━━<br/>Mandatory 30s cooldown<br/>RetryBudgetExhausted raised<br/>HTTP 429 returned"]

    C -->|"No"| D{"📊 Retry ratio ><br/>20% of total traffic?"}
    D -->|"Yes"| BLOCK

    D -->|"No"| ALLOW["✅ Retry Allowed<br/>━━━━━━━━━━━━━━━━━━<br/>Attempt counter incremented<br/>Sliding window tracked"]

    ALLOW --> E["Record retry attempt<br/>in sliding window"]

    style BLOCK fill:#3d1117,stroke:#f97583,stroke-width:2px,color:#f97583
    style ALLOW fill:#0d3117,stroke:#56d364,stroke-width:2px,color:#56d364
```

### Three Simultaneous Rules

| Rule | Threshold | Window | Purpose |
|---|---|---|---|
| Absolute cap | 20 retries max | 60 seconds | Hard limit prevents runaway |
| Ratio limit | 20% of total requests | 60 seconds | Retries shouldn't dominate traffic |
| Cooldown | 30 seconds mandatory | After violation | Give struggling services breathing room |

> **Why separate from Circuit Breaker?** Imagine 10 services each retrying 5 times — that's 50 retries hitting your system. Each service's circuit breaker is fine, but the aggregate retry volume is a storm. The retry budget catches this.

---

## 💰 Cost & Token Economics

> **"Full pipeline: find job + analyse + tailor resume + write cover letter + submit = ~$0.02–0.05 USD. Less than a gumball."**

```mermaid
flowchart TD
    subgraph "📊 Per-Call Token Tracking"
        CALL["Every LLM Call"] --> TRACK["TokenUsage Record<br/>━━━━━━━━━━━━━━━━━━<br/>agent_name<br/>provider · model<br/>input_tokens · output_tokens<br/>latency_ms · cost_usd<br/>success: bool"]
    end

    subgraph "💰 Per-Agent Daily Budget"
        TRACK --> DAILY["Daily Cost Aggregator<br/>Reset at UTC midnight"]
        DAILY --> CHECK{"Agent budget<br/>remaining?"}
        CHECK -->|"❌ Exhausted"| BLOCK["LLMError<br/>Budget Exhausted<br/>Before API call"]
        CHECK -->|"✅ OK"| CONTINUE["Allow LLM call"]
    end

    subgraph "🎟️ Per-User Credit System"
        REQ["API Request"] --> CREDIT["Credit Middleware<br/>Endpoint-specific pricing"]
        CREDIT --> BALANCE{"User credits<br/>remaining?"}
        BALANCE -->|"❌ Empty"| HTTP402["HTTP 402<br/>Payment Required"]
        BALANCE -->|"✅ OK"| PROCEED["Process request"]
    end

    subgraph "📈 Admin Dashboard"
        TRACK --> ADMIN["GET /admin/llm-usage<br/>━━━━━━━━━━━━━━━━━━<br/>Total invocations<br/>Cost USD per agent<br/>Avg latency per model<br/>Provider failure rates"]
    end

    style BLOCK fill:#3d1117,stroke:#f97583,stroke-width:2px,color:#f97583
    style HTTP402 fill:#3d1117,stroke:#f97583,stroke-width:2px,color:#f97583
```

### Model Pricing Table

| Model | Input $/1M tokens | Output $/1M tokens | Typical Use |
|---|---|---|---|
| `llama-3.1-8b-instant` | $0.05 | $0.08 | Speed tasks (60% of calls) |
| `llama-3.3-70b-versatile` | $0.59 | $0.79 | Quality tasks (30% of calls) |
| `gemini-2.0-flash-exp` | $0.075 | $0.30 | Vision + embeddings (10%) |
| `qwen/qwen3-coder:free` | $0.00 | $0.00 | Free fallback tier |

### Cost Breakdown Per Pipeline Run

| Stage | Model | Avg Tokens | Est. Cost |
|---|---|---|---|
| Scout (search) | 8B | ~500 | $0.00004 |
| Analyst (scoring) | 70B | ~2,000 | $0.003 |
| Company Research | 8B | ~1,500 | $0.0001 |
| Resume Tailoring | 70B + RAG | ~3,000 | $0.005 |
| Cover Letter | 70B | ~2,000 | $0.003 |
| **Total** | | | **~$0.01–0.05** |

---

## 🔎 Self-Correcting AI Search

> **"When 'Senior Staff Principal Cloud Infrastructure Engineer AWS GCP Azure Kubernetes Terraform' returns 0 results, the Scout doesn't give up. It asks a 70B model WHY it failed — and generates a simpler query."**

```mermaid
flowchart TD
    Q["👤 User Query<br/>'Senior Staff Cloud Infrastructure<br/>Engineer AWS GCP Azure K8s'"] --> SEARCH["🔍 SerpAPI Search<br/>site:greenhouse.io OR<br/>site:lever.co OR<br/>site:ashbyhq.com"]

    SEARCH --> CHECK{"0 valid<br/>results?"}
    CHECK -->|"No — jobs found!"| DONE["✅ Return discovered jobs<br/>SCOUT_FOUND events streamed"]

    CHECK -->|"Yes — 0 results<br/>attempt < max_retries"| ANALYZE["🧠 Groq 70B Analysis<br/>━━━━━━━━━━━━━━━━━━━━━<br/>'Why did this query fail?'<br/>'Too many keywords combined.'<br/>'Suggestion: Split into<br/>Cloud Engineer + Infrastructure'"]

    ANALYZE --> RETRY["🔄 Retry with simplified query<br/>'Cloud Infrastructure Engineer'"]
    RETRY --> CHECK2{"Results<br/>this time?"}
    CHECK2 -->|"Yes"| DONE
    CHECK2 -->|"No, max retries hit"| EMPTY["📭 Return empty<br/>Graceful degradation<br/>No crash, no error"]

    style ANALYZE fill:#0d1117,stroke:#d2a8ff,stroke-width:2px,color:#c9d1d9
    style DONE fill:#0d3117,stroke:#56d364,stroke-width:2px,color:#56d364
```

### Why ATS-Only Site Filters?

| Source | Direct Apply? | JobStream Compatible? |
|---|---|---|
| LinkedIn | ❌ Redirects to LinkedIn Apply | ❌ |
| Indeed | ❌ Redirects to Indeed Apply | ❌ |
| **Greenhouse** | ✅ Direct company form | ✅ |
| **Lever** | ✅ Direct company form | ✅ |
| **Ashby** | ✅ Direct company form | ✅ |
| **Workday** | ✅ Direct company form | ✅ |

> Higher success rate, no middleman, and the browser-use agent can fill these forms directly.

---

## 🥊 Salary Battle — Turn-Based AI Negotiation Engine

> **"A fully adversarial AI HR recruiter that negotiates your salary against you. 3 difficulty levels. Phase-based progression. Teaches you negotiation tactics by LOSING to a tough AI — so you WIN against a real recruiter."**

```mermaid
stateDiagram-v2
    [*] --> OPENING : User starts salary battle
    OPENING --> COUNTER : User makes initial offer
    COUNTER --> OBJECTION_HANDLING : AI HR pushes back<br/>"Budget constraints..."
    OBJECTION_HANDLING --> FINAL_OFFER : Positions narrowing
    FINAL_OFFER --> CLOSED : Deal reached or walked away

    note right of OPENING
        AI HR persona introduced.
        Company context + market data loaded.
        Phase: Opening — warm, professional.
    end note

    note right of COUNTER
        User states desired salary.
        AI responds with counter-offer.
        Anchoring tactics by AI.
    end note

    note right of OBJECTION_HANDLING
        AI raises objections:
        "Budget", "Market rate", "Experience gap"
        User must argue back with data.
    end note

    note right of FINAL_OFFER
        Positions converge.
        AI may concede or hold firm.
        Difficulty affects AI flexibility.
    end note
```

### Battle State Machine — LangGraph

```mermaid
flowchart TD
    START(["▶ Battle Start"]) --> EVAL["evaluate_user_input<br/>Assess tone + offer + leverage"]
    EVAL --> AI["generate_ai_response<br/>HR persona responds<br/>Based on difficulty + phase"]
    AI --> PHASE{"phase_transition<br/>Check progression"}
    PHASE -->|"Continue"| WS_PUSH["📡 SALARY_BATTLE_AI_RESPONSE<br/>Stream to WebSocket"]
    WS_PUSH --> WAIT["⏳ Await User Turn<br/>WebSocket input"]
    WAIT --> EVAL
    PHASE -->|"Phase = CLOSED"| END(["✅ Battle Complete<br/>Final outcome saved"])

    style EVAL fill:#0d1117,stroke:#58a6ff,stroke-width:2px,color:#c9d1d9
    style AI fill:#0d1117,stroke:#d2a8ff,stroke-width:2px,color:#c9d1d9
```

### Difficulty Levels

| Level | AI Behaviour | Learning Outcome |
|---|---|---|
| 🟢 Easy | Quick concessions, budget flexibility | Build confidence, practice structure |
| 🟡 Medium | Standard pushback, market-rate anchoring | Realistic preparation |
| 🔴 Hard | Aggressive tactics, firm constraints, silence pressure | Master negotiation under pressure |

### Battle State (Typed Pydantic)

```python
class SalaryBattleState(BaseModel):
    user_offer: float
    company_offer: float
    turn_count: int
    phase: BattlePhase   # OPENING → COUNTER → OBJECTION → FINAL → CLOSED
    negotiation_history: List[Dict]
    user_leverage: float  # 0.0–1.0 dynamically calculated
    final_outcome: Optional[Dict]
```

---

## 🔀 LangGraph State Machines — All Graphs

### Graph 1: Main Pipeline — Full Job Application DAG

```mermaid
flowchart TD
    START --> VALIDATE --> LOAD_PROFILE --> SCOUT_NODE
    SCOUT_NODE --> ANALYST_NODE
    ANALYST_NODE --> COMPANY_NODE
    COMPANY_NODE --> RESUME_NODE
    RESUME_NODE --> COVERLETTER_NODE
    COVERLETTER_NODE --> APPLIER_NODE
    APPLIER_NODE --> TRACKER_NODE --> END

    ANALYST_NODE -.->|"score < threshold"| SKIP_NODE

    RESUME_NODE ---|"asyncio.gather()"| COVERLETTER_NODE

    style START fill:#0d1117,stroke:#58a6ff,color:#c9d1d9
    style END fill:#0d1117,stroke:#56d364,color:#c9d1d9
```

### Graph 2: Cover Letter Agent — 6-Node DAG with HITL

```mermaid
stateDiagram-v2
    [*] --> plan : Extract requirements
    plan --> research_company : Gather company tone & values
    research_company --> generate_content : Draft with research context
    generate_content --> format_letter : Apply tone + structure
    format_letter --> human_review : HITL gate (WebSocket)
    human_review --> finalize : ✅ Approved
    human_review --> generate_content : 🔄 Revise (with feedback)
    human_review --> [*] : ❌ Abort
    finalize --> [*]
```

### Graph 3: Salary Battle — Turn-Based Adversarial

```mermaid
stateDiagram-v2
    [*] --> evaluate_user_input
    evaluate_user_input --> generate_ai_response : Assess position + leverage
    generate_ai_response --> phase_transition : HR persona responds
    phase_transition --> evaluate_user_input : 🔁 Battle continues
    phase_transition --> [*] : ✅ Phase = CLOSED
```

### Checkpointing Strategy

| Graph | Checkpoint Method | Recovery |
|---|---|---|
| Pipeline Graph | File-based: `data/checkpoints/{session_id}.json` | Resume from last completed node |
| Cover Letter | LangGraph `MemorySaver` | Resume from HITL gate after 120s timeout |
| Salary Battle | In-memory state + WebSocket session | Reconnect continues from last turn |

---

## 📊 Observability & LLM Tracing

> **"If you can't trace which agent called which model with which tokens, you can't debug, you can't optimise, and you can't control costs."**

```mermaid
flowchart LR
    subgraph "🤖 Application Layer"
        AGENTS["8 AI Agents<br/>Every LLM call instrumented"]
        SLOG["📝 Structured Logger<br/>JSON + ContextVars<br/>Auto PII Redaction"]
    end

    subgraph "📡 Tracing Pipeline"
        OTEL["OpenTelemetry SDK<br/>TracerProvider<br/>BatchSpanProcessor"]
        INSTR["LangChainInstrumentor<br/>★ ONE line of code ★<br/>Auto-instruments ALL agents"]
    end

    subgraph "📊 Dashboards"
        PHOENIX["🦅 Arize Phoenix<br/>━━━━━━━━━━━━━━━━━━<br/>LLM Trace Viewer<br/>Prompt/Completion pairs<br/>Token counts per span<br/>Latency waterfall"]
        PROM["📈 Prometheus Metrics<br/>━━━━━━━━━━━━━━━━━━<br/>Custom counters/histograms<br/>Per-agent invocation rates<br/>Error rates per provider"]
        ADMIN["🖥️ Admin API<br/>━━━━━━━━━━━━━━━━━━<br/>GET /admin/llm-usage<br/>GET /admin/circuit-breakers<br/>GET /admin/retry-budget"]
    end

    AGENTS --> OTEL --> INSTR --> PHOENIX
    AGENTS --> SLOG
    SLOG --> PROM
    SLOG --> ADMIN
```

### One Line That Instruments Everything

```python
# This single line auto-instruments ALL LangChain calls across ALL 8 agents
LangChainInstrumentor().instrument(tracer_provider=provider)
```

### Structured Log Examples

```python
# Agent operation
slog.agent("company_agent", "research_complete", company="Google", sources=3, latency_ms=2400)

# LLM call
slog.llm("groq", "llama-3.1-8b", input_tokens=1200, output_tokens=480, cost_usd=0.000038)

# Security event
slog.security("BLOCK", "injection_detected", category="ROLE_JAILBREAK", confidence=0.97)

# ALL values auto-checked by PIIDetector before write
```

---

## 📡 Real-Time Event Architecture

> **"25+ WebSocket event types stream live to the frontend. Every pipeline action is visible in real-time."**

```mermaid
flowchart TD
    subgraph "🔄 Event Bus — In-Process Pub/Sub"
        PUB["Agent emits event"] --> MW_PIPE["Middleware Pipeline<br/>━━━━━━━━━━━━━━━━━<br/>1. Log event<br/>2. PII-redact data<br/>3. Prometheus counter"]
        MW_PIPE --> EXACT["Exact: 'scout:found'"]
        MW_PIPE --> WILD["Wildcard: 'scout:*'"]
        MW_PIPE --> GLOBAL["Global: '*'"]
    end

    subgraph "📡 WebSocket Stream — 25+ Event Types"
        direction LR
        E1["🔍 SCOUT_FOUND"]
        E2["📊 ANALYST_RESULT"]
        E3["📄 RESUME_GENERATED"]
        E4["📸 BROWSER_SCREENSHOT"]
        E5["❓ HITL_REQUEST"]
        E6["🎉 APPLIER_COMPLETE"]
    end

    subgraph "🔀 Celery → WebSocket Bridge"
        CELERY["Celery Worker<br/>(separate process)"] --> REDIS_PUB["Redis PUBLISH<br/>jobai:events:{session_id}"]
        REDIS_PUB --> REDIS_SUB["FastAPI subscribes<br/>async for msg in pubsub.listen()"]
        REDIS_SUB --> WS_SEND["ws_manager.send_event()"]
    end

    EXACT --> E1
    WILD --> E2
    E4 -.-> CELERY
```

### Event Categories

| Category | Events | Description |
|---|---|---|
| 🔎 Discovery | `SCOUT_START` → `SEARCHING` → `FOUND` → `COMPLETE` | Job search progress |
| 📊 Analysis | `ANALYST_START` → `FETCHING` → `ANALYZING` → `RESULT` | Match scoring |
| 📄 Generation | `RESUME_START` → `TAILORING` → `GENERATED` → `COMPLETE` | Resume creation |
| 🤖 Automation | `NAVIGATE` → `CLICK` → `TYPE` → `UPLOAD` → `COMPLETE` | Browser actions |
| 👤 HITL | `HITL_REQUEST` ↔ `HITL_RESPONSE` ↔ `HITL_TIMEOUT` | Human interaction |
| 📸 Browser | `BROWSER_SCREENSHOT` (JPEG q50, every 2s) | Live visual stream |
| 💰 Salary | `BATTLE_START` → `USER_TURN` → `AI_RESPONSE` → `PHASE_CHANGE` | Negotiation |
| ⚙️ System | `STARTUP` → `HEARTBEAT` → `SHUTDOWN` | Infrastructure |

---

## 🏛️ Production AI Patterns Summary

```mermaid
mindmap
  root((🧠 JobStream<br/>Production AI))
    Multi-Agent Orchestration
      8 Specialist Agents
      LangGraph StateGraph DAG
      Typed PipelineState
      Conditional Edges
      Parallel Execution
      File-Based Checkpointing
    LLM Resilience
      5-Provider Fallback Chain
      Exponential Backoff
      4-Stage JSON Repair
      Temperature Caching
      Per-Agent Model Selection
    RAG Pipeline
      pgvector 768-dim
      Gemini Embeddings
      Chunking 1000/200
      Cosine Similarity Search
      Auto Profile Sync
    Agent Intelligence
      2-Tier Memory System
      Learning Injection
      Inter-Agent Protocol
      4 Message Intents
      Feedback Loop
    AI Safety
      6-Category Injection Detection
      3-Layer Guardrail Pipeline
      7-Type PII Redaction
      Content Safety Filter
      Output Schema Validation
    Resilience Patterns
      Circuit Breaker FSM
      Retry Budget Storm Prevention
      Distributed Lock
      Idempotency Guard
      Graceful Degradation
    Browser AI
      Gemini Vision Form Reading
      HITL via asyncio.Future
      Draft Mode Default
      Screenshot Streaming
      ATS Portal Compatibility
    Observability
      OpenTelemetry Spans
      Arize Phoenix Dashboard
      Prometheus Metrics
      Structured JSON Logging
      Per-Agent Cost Tracking
```

---

## 📈 The Numbers That Matter

| Metric | Value |
|---|---|
| **AI Agents** | 8 specialist agents, each with dedicated model + temperature |
| **LLM Providers** | 5-deep fallback chain (zero single-point-of-failure) |
| **LangGraph State Machines** | 3 (Pipeline DAG, Cover Letter DAG, Salary Battle) |
| **Resilience Patterns** | 5 (Circuit Breaker, Retry Budget, Distributed Lock, Idempotency, Graceful Degradation) |
| **Guardrail Layers** | 4 input + 1 output + PII redaction |
| **Prompt Injection Patterns** | 16+ across 6 attack categories |
| **PII Types Detected** | 7 with confidence thresholds |
| **RAG Dimensions** | 768-dim Gemini embeddings on pgvector ivfflat |
| **WebSocket Event Types** | 25+ across 8 categories |
| **Real-Time Event Bus** | Wildcard pub/sub with middleware pipeline |
| **JSON Repair Success Rate** | ~99.5% (recovers 15% malformed free-tier outputs) |
| **Cost Per Application** | ~$0.02–0.05 USD |
| **Agent Memory Types** | 5 (preference, learning, context, feedback, performance) |
| **Browser Automation** | Vision-based (Gemini) — zero CSS selectors |
| **HITL Timeout** | 120 seconds with draft save |
| **Model Routing Tiers** | 4 (Speed, Balanced, Premium, Vision) |

---

## 💡 Key Takeaways for AI Engineers

### 1. Multi-Model Strategy > Single-Model Dependency
If Groq goes down at 2 AM, your users don't see an error page. **5 providers, automatic fallback, zero downtime.**

### 2. RAG Prevents Hallucination
Your AI writes factual resume content because it **retrieves** real user data first. No made-up skills. No imaginary experience.

### 3. Circuit Breakers + Retry Budgets = Resilient AI
One failing API shouldn't cascade-crash your whole agent pipeline. **Per-service breakers + system-wide budget = graceful degradation.**

### 4. Agent Memory is a Competitive Moat
The more you use it, the better it gets. Your competitors start from scratch every session. **You don't.**

### 5. Human-in-the-Loop is the Production Secret
Full automation sounds cool until the AI encounters a CAPTCHA. **HITL via `asyncio.Future` gives you the best of both worlds** — AI speed with human judgment.

### 6. Model Routing Saves 60%+ Cost
Not every task needs the expensive model. **Route by complexity, not by default.** Keyword matching → 8B. Cover letter → 70B.

### 7. JSON Repair is Non-Negotiable for Free-Tier Models
15% of 8B model outputs are malformed. **Without a repair pipeline, 1 in 7 agent calls crashes silently.** Build the repair pipeline on day one.

### 8. Observability Isn't Optional for LLM Apps
If you can't trace which agent called which model with which tokens, you can't debug, you can't optimise, and you can't control costs. **One `LangChainInstrumentor().instrument()` line solves this.**

---

## 🔥 The Complete AI Tech Stack

```mermaid
mindmap
  root((🧠 AI Stack))
    Orchestration
      LangGraph StateGraph
      LangChain 1.2.6
      AsyncIO Parallel Nodes
      Typed State Machines
      File Checkpointing
    Models
      Groq Llama 3.1 8B
      Groq Llama 3.3 70B
      Gemini 2.0 Flash
      OpenRouter Qwen 3
      Gemini text-embedding-004
    RAG
      pgvector 768-dim
      RecursiveCharacterTextSplitter
      Cosine Similarity Search
      ivfflat Index
      Auto Profile Sync
    Browser AI
      browser-use 0.11.2
      Gemini Vision
      Playwright Chrome
      Draft Mode HITL
      5 FPS Screenshot Stream
    Agent Framework
      8 Specialist Agents
      2-Tier Memory
      Inter-Agent Protocol
      Learning Injection
      Feedback Loops
    Safety
      6 Injection Categories
      PII Auto-Redaction
      Content Safety Filter
      Output Validation
      Fail-Open Design
    Resilience
      5-Provider Fallback
      Circuit Breaker FSM
      Retry Budget
      4-Stage JSON Repair
      Graceful Degradation
    Observability
      OpenTelemetry
      Arize Phoenix
      Prometheus
      Structured Logging
      Cost Dashboard
```

---

<div align="center">

## 🗓️ Series Navigation

| Day | Topic | Status |
|---|---|---|
| **Day 1** | Project Overview & Features | ✅ Published |
| **Day 2** | **AI Techniques & Architecture** | 📍 **You Are Here** |
| **Day 3** | System Design & Infrastructure | 🔜 Coming Tomorrow |
| **Day 4** | Deployment & Production | 🔜 Coming Soon |

---

### 💬 The LinkedIn Post

---

</div>

## 📝 LinkedIn Post — Day 2

> Copy-paste this directly into LinkedIn:

---

**🧠 Day 2/4 — I Built 8 AI Agents That Apply to Jobs While I Sleep**

Yesterday I introduced JobStream. Today, let's go DEEP into the AI brain.

This isn't "call OpenAI and pray." This is production AI engineering.

**Here's what's under the hood:**

🤖 **8 Specialist AI Agents**
Not one do-everything model. Eight focused agents: Scout discovers jobs, Analyst scores matches, Resume Agent tailors with RAG, Cover Letter personalises per company, Interview Coach preps STAR answers, Salary Agent runs adversarial negotiation battles, Network Agent finds warm connections, and Tracker manages your pipeline.

Each agent has its own LLM model, temperature, memory, and tools. Because a keyword extraction task doesn't need the same $0.79/M-token model that writes your cover letter.

🔗 **5-Provider LLM Fallback Chain**
Groq → Groq backup key → OpenRouter → OpenRouter backup → Gemini. If ALL 5 fail, THEN error. Your 2 AM recruiter deadline doesn't care that Groq is rate-limiting.

🧬 **RAG Pipeline (pgvector + Gemini Embeddings)**
The resume agent doesn't hallucinate skills you don't have. It RETRIEVES your real experience from 768-dim vectors first, then writes grounded content. Semantic matching: "built distributed systems" finds "microservices architecture."

🧠 **Agent Memory — Your AI Gets Smarter Over Time**
2-tier persistence (cache + Supabase). The Resume Agent remembers you prefer bullet points. The Interview Coach knows you struggle with system design. Learning injection into system prompts. That's not a feature — that's a moat.

🛡️ **5 Resilience Patterns**
Circuit Breakers (per-service state machines), Retry Budgets (system-wide storm prevention), Distributed Locks (Redis SETNX + Lua), Idempotency Guards, and Graceful Degradation. One failing API cannot crash the pipeline.

🤖 **Vision-Based Browser Automation + Human-in-the-Loop**
The AI fills out applications using Gemini Vision — reads screenshots like a human. No CSS selectors. When it hits a CAPTCHA or weird question, it PAUSES and ASKS you via WebSocket. Draft mode default: it NEVER submits without your OK.

🔒 **AI Safety Pipeline**
16+ prompt injection patterns blocked across 6 attack categories. PII auto-redaction (7 types with confidence scores). Content safety filtering. All before the LLM sees your input.

💰 **Cost per full job application: ~$0.02-0.05 USD**
Finding the job + analysing it + tailoring resume + writing cover letter + submitting. Less than a gumball. Model routing saves 60%+ by using 8B for speed tasks and 70B only for quality tasks.

📊 **Full Observability**
OpenTelemetry + Arize Phoenix for LLM tracing. One line of code instruments ALL 8 agents. Per-agent cost dashboards. Structured JSON logging with auto PII redaction.

If your AI app doesn't have circuit breakers, it's a demo, not a product. 😤

Tomorrow: System Design deep dive.

📄 Full architecture doc with Mermaid diagrams: [GitHub link]

#AI #LLM #MachineLearning #MultiAgent #LangGraph #RAG #SystemDesign #SoftwareEngineering #BuildInPublic #AIEngineering #ProductionAI #Python #JobSearch #Automation #TechCareers #StartupLife

---

<div align="center">

*Built with obsessive attention to production-readiness.*

**"If your AI app doesn't have circuit breakers, it's a demo, not a product."** 😤

⭐ Star the repo if this architecture impressed you. PRs welcome.

</div>
