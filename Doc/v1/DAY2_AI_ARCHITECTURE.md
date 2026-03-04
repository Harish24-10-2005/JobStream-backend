# 🧠 Day 2 — The AI Brain Behind JobStream

> **"I didn't just build an AI app. I built 8 AI agents, gave them memory, failure tolerance, a retry budget, and the ability to argue about salary — and they still cost less than my lunch."**

---

## 🎯 What This Post Covers

Day 1 was the intro. Today we go deep into **what makes JobStream's AI actually work in production** — not a demo, not a tutorial project, not "call OpenAI and pray."

This is multi-agent orchestration, RAG pipelines, circuit breakers, human-in-the-loop browser automation, model routing, and every resilience pattern I used to make sure the AI keeps working even when half the internet is down.

**Tech used:** LangGraph · Groq Llama 3 · Gemini 2.0 Flash · pgvector RAG · browser-use HITL · OpenTelemetry · AsyncIO · Pydantic v2

---

## 🏗️ High-Level AI Architecture

```mermaid
graph TB
    subgraph "🌐 User Interface"
        UI["Next.js Frontend<br/>WebSocket Real-time"]
    end

    subgraph "🛡️ Gateway Layer"
        MW["Middleware Stack<br/>Rate Limit → Credits → Auth"]
        GRD["AI Guardrails<br/>Prompt Injection Detection<br/>PII Redaction · XSS Filter"]
    end

    subgraph "🧠 AI Orchestration — LangGraph Pipeline"
        PG["StateGraph Engine<br/>Typed PipelineState<br/>Conditional Edges"]
        SP["Step Planner<br/>LLM-driven step selection"]
    end

    subgraph "🤖 8 Specialist AI Agents"
        SA["🔍 Scout<br/>SerpAPI + Self-Correcting Search"]
        AA["📊 Analyst<br/>HTML → Structured Job Analysis"]
        CA["🏢 Company Intel<br/>Culture + Risk Assessment"]
        RA["📄 Resume Agent<br/>RAG-Powered Tailoring"]
        CLA["✉️ Cover Letter<br/>Per-Company Personalisation"]
        IA["🎤 Interview Coach<br/>STAR + Technical Prep"]
        NA["🔗 Network Agent<br/>LinkedIn X-Ray Search"]
        TA["📋 Tracker<br/>Application CRM"]
    end

    subgraph "⚙️ Core AI Infrastructure"
        LLM["UnifiedLLM<br/>5-Provider Fallback Chain"]
        MEM["Agent Memory<br/>2-Tier Persist + Learning"]
        RAG["RAG Service<br/>pgvector + Gemini Embeddings"]
        MRP["Model Router<br/>Complexity-Based Selection"]
        AP["Agent Protocol<br/>Inter-Agent Messaging"]
    end

    subgraph "🛡️ Resilience Layer"
        CB["Circuit Breaker<br/>Per-Service State Machine"]
        RB["Retry Budget<br/>System-Wide Storm Prevention"]
        CT["Cost Tracker<br/>Per-Agent Daily Budgets"]
    end

    subgraph "🤖 Browser Automation"
        LIVE["Live Applier<br/>browser-use + Gemini Vision"]
        HITL["Human-in-the-Loop<br/>asyncio.Future via WebSocket"]
    end

    UI --> MW --> GRD --> PG
    SP --> PG
    PG --> SA --> AA --> CA --> RA --> CLA
    PG --> LIVE
    RA --> RAG
    SA & AA & CA & RA & CLA & IA --> LLM
    LLM --> CB --> RB
    LLM --> MRP
    SA & RA & IA --> MEM
    SA & CA & NA --> AP
    LIVE --> HITL --> UI
```

---

## 🔗 The 5-Provider LLM Fallback Chain

> Most AI apps: "Call OpenAI. If it fails, show error."  
> JobStream: "Call Groq. If rate-limited, try backup key. Still failing? OpenRouter. Still? Try second key. STILL? Gemini. If ALL fail, THEN show error."

```mermaid
flowchart LR
    A["Agent Request"] --> B["💰 Budget Check"]
    B -->|Exhausted| STOP["❌ Budget Exhausted"]
    B -->|OK| P1

    P1["🥇 Groq Primary<br/>llama-3.1-8b<br/>sub-200ms"] -->|429 Rate Limit| P2
    P1 -->|✅| SUCCESS["Return Response"]

    P2["🥈 Groq Fallback Key<br/>Same model, different quota"] -->|Fail| P3
    P2 -->|✅| SUCCESS

    P3["🥉 OpenRouter<br/>Qwen 3 Coder Free"] -->|Fail| P4
    P3 -->|✅| SUCCESS

    P4["4️⃣ OpenRouter Fallback<br/>Second API key"] -->|Fail| P5
    P4 -->|✅| SUCCESS

    P5["5️⃣ Gemini 2.0 Flash<br/>Last Resort + Vision"] -->|All Fail| FAIL["❌ All Providers Down"]
    P5 -->|✅| SUCCESS
```

### Why This Matters

| Feature | What It Does |
|---------|-------------|
| **Exponential Backoff** | 1s → 2s → 4s per provider before giving up |
| **JSON Repair Pipeline** | Strips markdown fences → extracts `{...}` → fixes trailing commas → repairs quotes |
| **Temperature Caching** | One singleton per temperature (0.0 for classification, 0.7 for creative) |
| **Token Tracking** | Every call records: agent, provider, model, tokens, latency, cost USD |

> **Fun fact:** Free-tier 8B models produce malformed JSON ~15% of the time. Without the 4-stage JSON repair pipeline, that's 1 in 7 agent calls crashing silently. 💀

---

## 🧩 Multi-Agent Pipeline — LangGraph StateGraph

> "Not a chain. Not a loop. A **typed, stateful DAG** with conditional edges and parallel execution."

```mermaid
flowchart TD
    START(["▶ Pipeline Start"]) --> VALIDATE["🔍 Validate Input<br/>Profile completeness check"]
    VALIDATE --> LOAD["📥 Load Profile<br/>Fetch from Supabase"]
    LOAD --> SCOUT["🔎 Scout Node<br/>SerpAPI + ATS site-filters<br/>+ LLM self-correction"]
    SCOUT --> ANALYZE["📊 Analyst Node<br/>HTML parsing + 70B analysis<br/>Match score 0-100"]

    ANALYZE --> COMPANY_CHECK{"🏢 Company<br/>Research?"}
    COMPANY_CHECK -->|Yes| COMPANY["Company Research<br/>Culture + Risk + Intel"]
    COMPANY_CHECK -->|No| RESUME_CHECK

    COMPANY --> RESUME_CHECK{"📄 Resume<br/>Tailoring?"}
    RESUME_CHECK -->|Yes| PARALLEL["⚡ Parallel Execution<br/>asyncio.gather()"]
    RESUME_CHECK -->|No| APPLY_CHECK

    PARALLEL --> RESUME["📄 Resume Agent<br/>RAG + LaTeX PDF"]
    PARALLEL --> COVER["✉️ Cover Letter<br/>Per-company personalised"]

    RESUME & COVER --> APPLY_CHECK{"🚀 Auto<br/>Apply?"}
    APPLY_CHECK -->|Yes| APPLY["🤖 Live Applier<br/>Browser automation + HITL"]
    APPLY_CHECK -->|No| TRACK

    APPLY --> TRACK["📋 Track Results<br/>Save to job_applications"]
    TRACK --> END(["✅ Pipeline Complete"])

    style PARALLEL fill:#1a1a2e,stroke:#e94560,stroke-width:2px
    style SCOUT fill:#1a1a2e,stroke:#0f3460,stroke-width:2px
    style APPLY fill:#1a1a2e,stroke:#e94560,stroke-width:2px
```

### Typed State — No "String Soup"

Every pipeline node reads and writes to a **Pydantic-validated `PipelineState`**:

```python
class PipelineState(BaseModel):
    query: str
    location: str
    min_match_score: int = 70        # Only process jobs above this
    auto_apply: bool = False
    job_urls: List[str]              # Populated by Scout
    current_analysis: JobAnalysis    # Populated by Analyst
    job_results: List[JobResult]     # Accumulated results
    node_statuses: Dict[str, NodeStatus]  # Per-node tracking
```

> No magic dictionaries. No `state["results"][0]["maybe_data"]`. Type errors caught at build time, not at 2 AM in production.

---

## 🔍 RAG — Retrieval-Augmented Generation

> "Your resume agent doesn't hallucinate experience you don't have. It **retrieves** your real experience first, then writes grounded content."

```mermaid
flowchart LR
    subgraph "📥 Indexing Phase (upload/update)"
        RESUME["User Resume"] --> SPLIT["RecursiveCharacterTextSplitter<br/>chunk_size=1000<br/>overlap=200"]
        SPLIT --> CHUNKS["50–200 chunks"]
        CHUNKS --> EMBED["Gemini text-embedding-004<br/>768-dim vectors"]
        EMBED --> DB["Supabase pgvector<br/>ivfflat cosine index"]
    end

    subgraph "🔎 Query Phase (per job application)"
        JOB["Job Requirements"] --> QEMBED["Embed query → 768-dim"]
        QEMBED --> SEARCH["match_documents() RPC<br/>cosine similarity"]
        SEARCH --> TOP["Top-K relevant chunks"]
        TOP --> INJECT["Inject into LLM prompt<br/>as grounded context"]
        INJECT --> GENERATE["Resume Agent generates<br/>tailored content"]
    end
```

### Why These Chunk Params?

| Param | Value | Reason |
|-------|-------|--------|
| `chunk_size` | 1,000 chars | ≈200 tokens — multiple chunks fit in 4K context |
| `overlap` | 200 chars | Prevents skills split across chunk boundaries from being lost |
| `embedding_dim` | 768 | Gemini `text-embedding-004` native dimension |
| `index` | ivfflat | Approximate nearest neighbor — fast at scale |

> **Semantic matching wins:** "built distributed systems" matches "microservices architecture" — keyword matching would miss this entirely.

---

## 🔄 Circuit Breaker — Per-Service Resilience

> "When SerpAPI is down, don't wait 30s for each timeout. **Trip the breaker** and skip it for 60s. Keep the system fast."

```mermaid
stateDiagram-v2
    [*] --> CLOSED : System starts healthy

    CLOSED --> OPEN : failures >= threshold<br/>within sliding window

    OPEN --> HALF_OPEN : recovery_timeout elapsed<br/>(60 seconds)

    HALF_OPEN --> CLOSED : ✅ Probe call succeeds
    HALF_OPEN --> OPEN : ❌ Probe call fails

    note right of CLOSED
        All calls pass through.
        Failures tracked in
        sliding deque(maxlen=1000).
    end note

    note right of OPEN
        All calls fail-fast.
        Fallback function called.
        rejected_count incremented.
    end note

    note right of HALF_OPEN
        ONE probe call allowed.
        Success → recovery.
        Failure → re-open.
    end note
```

### Per-Service Breaker Config

| Service | Threshold | Recovery | Why |
|---------|-----------|----------|-----|
| `groq` | 5 failures | 60s | Primary LLM — needs fast recovery |
| `openrouter` | 5 failures | 60s | Fallback LLM — same logic |
| `gemini` | 3 failures | 30s | Vision + embeddings — critical for applier |
| `serpapi` | 3 failures | 30s | Paid API — fail fast to save money |
| `supabase` | 5 failures | 60s | Database — everything depends on this |

### + Retry Budget (System-Wide Storm Prevention)

```mermaid
flowchart TD
    A["Circuit Breaker wants to retry"] --> B{"Total retries in<br/>last 60s > 20?"}
    B -->|Yes| BLOCK["🛑 BLOCKED<br/>30s cooldown"]
    B -->|No| C{"Retry ratio<br/>> 20% of traffic?"}
    C -->|Yes| BLOCK
    C -->|No| ALLOW["✅ Retry allowed"]
```

> **Why separate from Circuit Breaker?** CB controls per-service failure detection. Retry Budget prevents the **act of retrying** from making things worse across the **entire system**. They're complementary.

---

## 🤖 Browser Automation + Human-in-the-Loop

> "The AI fills out job applications in a real browser. When it hits a CAPTCHA or a weird question, it **pauses and asks you** — then resumes when you answer."

```mermaid
sequenceDiagram
    participant BA as 🤖 Browser Agent<br/>(Gemini Vision)
    participant LS as Live Applier
    participant WS as WebSocket Manager
    participant UI as 👤 User Browser

    BA->>LS: Navigate to job URL
    LS->>UI: 📸 Screenshot stream (every 2s)

    BA->>BA: Fill name, email, phone...
    LS->>UI: 📸 Screenshot: form filling

    BA->>LS: ❓ ask_human("What team interests you?")
    LS->>WS: emit HITL_REQUEST + hitl_id
    WS->>UI: WebSocket push → show dialog

    UI->>WS: User types answer
    WS->>LS: resolve_hitl(hitl_id, answer)
    LS->>LS: asyncio.Future.set_result(answer)
    LS->>BA: ActionResult("Human responded: ...")

    BA->>BA: Continue filling form...
    BA->>LS: Form complete → DRAFT_REVIEW
    LS->>UI: 👀 "Review before submit?"
    UI->>WS: ✅ Confirm
    BA->>BA: Click Submit
    LS->>UI: 🎉 APPLIER_COMPLETE
```

### Why browser-use Over Selenium?

| Approach | How It Finds Fields | Breaks When... |
|----------|-------------------|----------------|
| **Selenium** | `By.ID("firstName")` | Company updates their form HTML |
| **Playwright** | `page.locator("#firstName")` | Same — brittle CSS selectors |
| **browser-use** | LLM sees the screenshot and decides | Almost never — it reads like a human |

### Draft Mode State Machine

```mermaid
stateDiagram-v2
    [*] --> FILLING : Apply started
    FILLING --> FILLED : All fields complete
    FILLED --> AWAITING_REVIEW : emit DRAFT_REVIEW<br/>await asyncio.Future
    AWAITING_REVIEW --> SUBMITTING : ✅ User confirms
    AWAITING_REVIEW --> EDITING : ✏️ User edits
    SUBMITTING --> COMPLETE : Form submitted
    EDITING --> [*] : Human takes over
    COMPLETE --> [*]
```

---

## 🧠 Agent Memory — Persistent Learning

> "Your AI agents **remember** your preferences. The Resume Agent learns you prefer bullet points. The Interview Coach remembers you struggle with system design questions."

```mermaid
flowchart LR
    subgraph "Write Path"
        REMEMBER["agent.remember(key, value)"] --> CACHE["In-Memory Dict<br/>fast, volatile"]
        REMEMBER --> SUPA["Supabase<br/>agent_memories table"]
    end

    subgraph "Read Path"
        RECALL["agent.recall(key)"] --> HIT{"Cache hit?"}
        HIT -->|Yes| CHECK["Check expiry → return"]
        HIT -->|No| FETCH["Query Supabase<br/>→ populate cache"]
    end

    subgraph "Learning Loop"
        FEEDBACK["agent.record_feedback(rating)"] --> LEARN["agent_feedback table"]
        LEARN --> INJECT["get_learnings()<br/>→ inject into system prompt"]
    end
```

### Memory Types

| Type | Purpose | Example |
|------|---------|---------|
| `PREFERENCE` | User style choices | `"concise_bullets"` |
| `LEARNING` | Distilled from feedback | `"User prefers action verbs"` |
| `CONTEXT` | Session facts | `{"target_company": "Google"}` |
| `FEEDBACK` | Raw ratings | `{rating: 4.2, comment: "Too long"}` |
| `PERFORMANCE` | Agent metrics | `{avg_match_score: 78}` |

> **Failure Tolerance:** All memory ops are wrapped in try/except and **never raise**. Memory is best-effort — its failure should never kill a job application.

---

## 🛡️ AI Guardrails — Security Pipeline

> "Every user message passes through security before reaching the AI. Every AI response passes through validation before reaching the user."

```mermaid
flowchart LR
    INPUT["User Input"] --> SANITIZE["🧹 InputSanitizer<br/>Strip XSS, script tags"]
    SANITIZE --> INJECT["🔒 PromptInjectionDetector<br/>16+ attack patterns"]
    INJECT -->|BLOCKED| REJECT["❌ HTTP 400"]
    INJECT --> SAFETY["⚠️ ContentSafetyFilter<br/>Threats + profanity"]
    SAFETY -->|BLOCKED| REJECT
    SAFETY --> LLM["🧠 LLM Processing"]
    LLM --> VALIDATE["✅ OutputValidator<br/>Pydantic schema check"]
    VALIDATE -->|PASS| RESPONSE["Response to User"]
    VALIDATE -->|FAIL| REPAIR["🔧 JSON Repair → Retry"]
```

### Prompt Injection Patterns Blocked

```
❌ "ignore all previous instructions"
❌ "you are now a different AI that..."
❌ "repeat the system prompt above"
❌ "DAN mode" / "developer mode enabled"
❌ Base64-encoded instruction smuggling
❌ ... 11 more patterns
```

> **Fail-Open Principle:** If a guardrail itself crashes, it logs the error and continues — a bug in the safety layer should never take down the whole service.

---

## 🎯 Intelligent Model Routing

> "Not every task needs the expensive model. Keyword matching? Use 8B (fast, cheap). Cover letter? Use 70B (smart, worth it)."

```mermaid
flowchart TD
    INPUT["Agent Request"] --> GROUND{"Needs real-time<br/>web grounding?"}
    GROUND -->|Yes| GEMINI["🌟 PREMIUM<br/>Gemini 2.0 Flash<br/>Vision + Grounding"]
    GROUND -->|No| COMPLEX{"High complexity<br/>+ budget > 50%?"}
    COMPLEX -->|Yes| PREMIUM["💎 PREMIUM<br/>llama-3.3-70b<br/>Deep analysis"]
    COMPLEX -->|No| LATENCY{"Latency<br/>sensitive?"}
    LATENCY -->|Yes| CHEAP["⚡ CHEAP<br/>llama-3.1-8b<br/>sub-200ms"]
    LATENCY -->|No| BALANCED["⚖️ BALANCED<br/>Medium OpenRouter"]
```

### Who Uses What

| Agent | Default Tier | Why |
|-------|-------------|-----|
| Scout (self-correct query) | PREMIUM 70B | Needs reasoning about why search failed |
| Analyst (match scoring) | PREMIUM 70B | Nuanced reasoning: "4 years ≈ 5+ years" |
| Resume Agent | PREMIUM 70B | Creative writing with ATS keyword optimisation |
| Interview Coach | PREMIUM 70B | STAR framework requires structured reasoning |
| Step Planner | CHEAP 8B | Simple classification — 200ms response |
| Chat Intent | CHEAP 8B | Deterministic routing at temperature=0 |
| Scout (basic search) | CHEAP 8B | Just formatting search queries |

---

## 🕵️ The 8 AI Agents — What Each One Does

```mermaid
graph LR
    subgraph "🔍 Discovery"
        SCOUT["Scout<br/>SerpAPI + Self-Correcting<br/>ATS Site Filters"]
        ANALYST["Analyst<br/>HTML → JobAnalysis<br/>Match Score 0-100"]
    end

    subgraph "🏢 Intelligence"
        COMPANY["Company Intel<br/>Culture + Glassdoor<br/>+ Risk Assessment"]
        NETWORK["Network Agent<br/>LinkedIn X-Ray<br/>Warm Connections"]
    end

    subgraph "📝 Generation"
        RESUME["Resume Agent<br/>RAG + LaTeX → PDF<br/>ATS Keyword Optimization"]
        COVER["Cover Letter<br/>Per-Company<br/>Personalised"]
    end

    subgraph "🎯 Preparation"
        INTERVIEW["Interview Coach<br/>STAR + Technical<br/>System Design for Sr."]
        SALARY["Salary Battle<br/>AI Recruiter Negotiation<br/>3 Difficulty Levels"]
    end

    subgraph "🤖 Action"
        APPLIER["Live Applier<br/>Browser Automation<br/>Draft Mode + HITL"]
        TRACKER["Tracker<br/>Application CRM<br/>Follow-up Reminders"]
    end

    SCOUT --> ANALYST --> COMPANY --> RESUME --> COVER --> APPLIER --> TRACKER
    ANALYST --> INTERVIEW
    ANALYST --> SALARY
    COMPANY --> NETWORK
```

### Agent Communication Protocol

Agents don't work in isolation — they **talk to each other**:

```mermaid
sequenceDiagram
    participant CO as 🏢 Company Agent
    participant CL as ✉️ Cover Letter
    participant RA as 📄 Resume Agent
    participant MEM as 🧠 Agent Memory

    CO->>CO: Research "Acme Corp"
    CO-->>CL: INFORM: "Culture is toxic per Glassdoor"
    CO-->>RA: INFORM: "They value Python + Kubernetes"
    CL->>CL: Adjust tone (cautious, professional)
    RA->>RA: Prioritise K8s experience in bullet points
    RA->>MEM: FEEDBACK: "User rated output 4/5"
    MEM-->>RA: LEARNING: "Continue current approach"
```

| Intent | Direction | Example |
|--------|-----------|---------|
| `INFORM` | Broadcast | Company → All: "High turnover at Acme" |
| `REQUEST` | Direct | Cover Letter → Company: "Get culture brief for Google" |
| `DELEGATE` | Hand off | Pipeline → Network: "Find contacts at this company" |
| `FEEDBACK` | Quality signal | Resume → Memory: "User rated 4/5" |

---

## 🔎 Scout Agent — Self-Correcting Search

> "When `Senior Staff Principal Cloud Infrastructure Engineer AWS GCP Azure` returns 0 results, the Scout asks a 70B model WHY it failed — and generates a simpler query."

```mermaid
flowchart TD
    Q["User Query"] --> SEARCH["SerpAPI Search<br/>site:greenhouse.io OR<br/>site:lever.co OR<br/>site:ashbyhq.com"]
    SEARCH --> CHECK{"0 valid<br/>results?"}
    CHECK -->|No| DONE["✅ Return jobs"]
    CHECK -->|Yes, attempt < 2| LLM["🧠 Groq 70B:<br/>'Why did this fail?<br/>Generate broader query'"]
    LLM --> RETRY["Retry with<br/>simpler query"]
    RETRY --> CHECK2{"Results?"}
    CHECK2 -->|Yes| DONE
    CHECK2 -->|No| EMPTY["Return empty<br/>(graceful degradation)"]
```

> **Why ATS-only search?** LinkedIn/Indeed redirect to their own apply flows. Greenhouse, Lever, and Ashby give direct company apply pages — higher success rate, no middleman.

---

## 💰 Cost & Credit Management

```mermaid
flowchart TD
    subgraph "Per-Call Tracking"
        CALL["LLM Call"] --> TRACK["Token Tracker<br/>input_tokens + output_tokens"]
        TRACK --> COST["Cost Calculator<br/>MODEL_PRICING table"]
    end

    subgraph "Per-Agent Budget"
        COST --> DAILY["Daily Cost per Agent<br/>Reset at UTC midnight"]
        DAILY --> CHECK{"Budget<br/>remaining?"}
        CHECK -->|No| BLOCK["❌ LLMError:<br/>Budget exhausted"]
        CHECK -->|Yes| CONTINUE["✅ Allow call"]
    end

    subgraph "Per-User Credits"
        REQ["API Request"] --> CREDIT["Credit Middleware<br/>endpoint-specific pricing"]
        CREDIT --> BALANCE{"Credits<br/>remaining?"}
        BALANCE -->|No| HTTP402["HTTP 402<br/>Payment Required"]
        BALANCE -->|Yes| PROCEED["Process request"]
    end
```

| Model | Input $/1M tokens | Output $/1M tokens |
|-------|-------------------|---------------------|
| llama-3.1-8b-instant | $0.05 | $0.08 |
| llama-3.3-70b-versatile | $0.59 | $0.79 |
| gemini-2.0-flash-exp | $0.075 | $0.30 |
| qwen3-coder:free | $0.00 | $0.00 |

> **Full pipeline cost:** ~$0.02–0.05 per job application. That's finding the job, analysing it, tailoring your resume, writing a cover letter, and submitting. **Less than a gumball.**

---

## 📡 Real-Time Event System

```mermaid
flowchart TD
    subgraph "Event Bus (In-Process Pub/Sub)"
        PUB["scout:found event"] --> MW["Middleware Pipeline:<br/>1. Log event<br/>2. PII-redact data<br/>3. Prometheus metrics"]
        MW --> EXACT["Exact: 'scout:found'"]
        MW --> WILD["Wildcard: 'scout:*'"]
        MW --> GLOBAL["Global: '*'"]
    end

    subgraph "WebSocket (25+ Event Types)"
        direction LR
        E1["SCOUT_FOUND"]
        E2["ANALYST_RESULT"]
        E3["RESUME_GENERATED"]
        E4["BROWSER_SCREENSHOT"]
        E5["HITL_REQUEST"]
        E6["DRAFT_REVIEW"]
    end

    EXACT --> E1
```

### 25+ Real-Time Event Types

| Category | Events |
|----------|--------|
| 🔎 Scout | `SCOUT_START` → `SEARCHING` → `FOUND` → `COMPLETE` |
| 📊 Analyst | `ANALYST_START` → `FETCHING` → `ANALYZING` → `RESULT` |
| 📄 Resume | `RESUME_START` → `TAILORING` → `GENERATED` → `COMPLETE` |
| 🤖 Applier | `NAVIGATE` → `CLICK` → `TYPE` → `UPLOAD` → `COMPLETE` |
| 👤 HITL | `HITL_REQUEST` ↔ `HITL_RESPONSE` |
| 📸 Browser | `BROWSER_SCREENSHOT` (JPEG q50, every 2s) |

---

## 📊 Observability & Telemetry

```mermaid
flowchart LR
    APP["JobStream Backend"] --> OTEL["OpenTelemetry<br/>Auto-instrumented"]
    OTEL --> PHOENIX["Arize Phoenix<br/>LLM Trace Viewer"]
    APP --> PROM["Prometheus Metrics<br/>Custom Pure-Python"]
    PROM --> GRAFANA["Grafana Dashboard"]
    APP --> SLOG["Structured Logger<br/>JSON + PII Redaction"]
    SLOG --> CLOUD["CloudWatch / Datadog"]
```

> **One line of code** auto-instruments all LangChain calls across all 8 agents:
> ```python
> LangChainInstrumentor().instrument(tracer_provider=provider)
> ```

---

## 🏛️ Production Infrastructure Summary

| Pattern | Implementation | Why |
|---------|---------------|-----|
| **Circuit Breaker** | Per-service state machine (CLOSED → OPEN → HALF_OPEN) | Prevent cascading failures |
| **Retry Budget** | System-wide 20/min cap, 20% ratio max | Prevent retry storms |
| **Distributed Lock** | Redis SET NX + Lua atomic release | Prevent duplicate pipeline runs |
| **Idempotency Guard** | Redis key with 15-min TTL | Prevent double-click submissions |
| **Feature Flags** | SHA256 deterministic rollout | Safe gradual deployments |
| **Credit Budget** | Per-user daily allowance (queries + tokens) | Cost control per user |
| **PII Redaction** | Regex scanner (7 PII types, confidence thresholds) | GDPR/CCPA compliance |
| **AES-256-GCM** | Random nonce per encryption, authenticated tags | Credential security |
| **Graceful Shutdown** | EventBus → close WS → close Redis → reset DI | Zero data loss on deploy |

---

## 🎬 End-to-End Request Flow

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant WS as 🔌 WebSocket
    participant API as ⚡ FastAPI
    participant PG as 🧠 LangGraph
    participant S as 🔍 Scout
    participant AN as 📊 Analyst
    participant R as 📄 Resume
    participant APP as 🤖 Live Applier

    U->>API: POST /pipeline/start
    API->>API: Idempotency check (Redis)
    API->>API: Credit check (daily budget)
    API->>WS: Register session
    API->>PG: run_pipeline(state)

    PG->>S: scout_node()
    S-->>WS: 🔍 SCOUT_FOUND × N
    S-->>PG: job_urls populated

    PG->>AN: analyst_node()
    AN-->>WS: 📊 ANALYST_RESULT × N

    PG->>R: resume_node ‖ cover_letter_node
    R-->>WS: 📄 RESUME_GENERATED

    PG->>APP: applier_node()
    APP-->>WS: 📸 SCREENSHOT every 2s
    APP-->>WS: ❓ HITL_REQUEST
    U-->>WS: 💬 HITL answer
    WS-->>APP: asyncio.Future.set_result()
    APP-->>WS: 🎉 APPLIER_COMPLETE
```

---

## 📈 By The Numbers

| Metric | Value |
|--------|-------|
| **AI Agents** | 8 specialist agents |
| **LLM Providers** | 5-provider fallback chain |
| **Resilience Patterns** | 5 (circuit breaker, retry budget, distributed lock, idempotency, graceful degradation) |
| **Real-Time Events** | 25+ WebSocket event types |
| **Security Layers** | 7 middleware + 4 guardrails |
| **RAG Dimensions** | 768-dim Gemini embeddings on pgvector |
| **Cost Per Application** | ~$0.02–0.05 USD |
| **Agent Memory Types** | 5 (preference, learning, context, feedback, performance) |
| **PII Patterns Detected** | 7 types with confidence thresholds |
| **Prompt Injection Patterns** | 16+ blocked patterns |

---

## 🔥 The Tech Stack At A Glance

```mermaid
mindmap
  root((JobStream AI))
    AI/ML
      LangGraph StateGraph
      Groq Llama 3.1/3.3
      Gemini 2.0 Flash
      OpenRouter Qwen 3
      pgvector RAG
      Gemini Embeddings
      browser-use HITL
      STAR Framework
    Infrastructure
      FastAPI Async
      Redis Distributed Lock
      Celery Workers
      WebSocket Real-time
      Supabase PostgreSQL
      Pydantic v2 Strict
    Resilience
      Circuit Breaker
      Retry Budget
      5-Provider Fallback
      Idempotency Guard
      Graceful Degradation
    Security
      AI Guardrails
      PII Redaction
      AES-256-GCM
      Prompt Injection Detection
      Rate Limiting
    Observability
      OpenTelemetry
      Arize Phoenix
      Prometheus Metrics
      Structured Logging
      Cost Tracking
```

---

## 💡 Key Takeaways for AI Engineers

1. **Multi-model strategy > Single-model dependency.** If Groq goes down at 2 AM, your users don't see an error page.

2. **RAG prevents hallucination.** Your AI writes factual resume content because it **retrieves** real data first.

3. **Circuit breakers + Retry budgets = Resilient AI.** One failing API shouldn't cascade-crash your whole agent pipeline.

4. **Agent memory makes AI personal.** The more you use it, the better it gets. That's not a feature — that's a moat.

5. **Human-in-the-Loop is the production secret.** Full automation sounds cool until the AI encounters a CAPTCHA. HITL via `asyncio.Future` gives you the best of both worlds.

6. **Observability isn't optional for LLM apps.** If you can't trace which agent called which model with which tokens, you can't debug, you can't optimise, and you can't control costs.

---

<div align="center">

### 🧠 Day 2 of 4 — AI Architecture Deep Dive

**Day 1:** Project Overview & Features  
**Day 2:** AI Techniques & Architecture ← You are here  
**Day 3:** System Design & Infrastructure  
**Day 4:** Deployment & Production  

---

*Built with obsessive attention to production-readiness.*  
*If your AI app doesn't have circuit breakers, it's a demo, not a product.* 😤

**#AI #LLM #MachineLearning #MultiAgent #LangGraph #RAG #SystemDesign #SoftwareEngineering #OpenSource #BuildInPublic #AIEngineering #ProductionAI**

</div>
