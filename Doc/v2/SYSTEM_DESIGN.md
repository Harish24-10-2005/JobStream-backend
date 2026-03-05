# 🏗️ Day 3 — System Design Deep Dive
## JobStream: How to Architect a Production AI Platform That Actually Survives the Real World

> *"Anyone can build a demo. Very few can build a system that stays alive at 3 AM when Groq rate-limits, Redis hiccups, and two users accidentally double-click Apply at the same time."*

---

## 📐 The Big Picture — What We're Even Solving

JobStream is not a chatbot with a resume button. It's a **distributed, event-driven, multi-agent orchestration platform** built on these core constraints:

| Constraint | Reality |
|---|---|
| AI providers fail and rate-limit | We use 5 different LLM providers |
| Browser automation blocks | Celery isolates it in a dedicated process |
| Duplicate requests from UI | Idempotency guard rejects dupes |
| Concurrent sessions corrupt state | Distributed lock (Redis) prevents it |
| LLMs hallucinate bad JSON | 4-step repair pipeline before parse |
| Users submit private data | PII redaction before any log write |
| Costs spiral without control | Per-agent daily budget + credit middleware |

---

## 1️⃣ Overall System Architecture

```mermaid
graph TB
    subgraph "Client"
        UI["Next.js Frontend"]
    end

    subgraph "API Gateway — FastAPI"
        MW["Middleware Stack\nCORS → RateLimit → Credits → Auth"]
        REST["REST API v1"]
        WS["WebSocket Manager\nReal-time + HITL"]
    end

    subgraph "Pipeline Engine — LangGraph"
        PG["StateGraph\nTyped PipelineState"]
        N1["Scout Node"]
        N2["Analyst Node"]
        N3["Company Node"]
        N4["Resume Node"]
        N5["CoverLetter Node"]
        N6["Applier Node"]
    end

    subgraph "Core Infrastructure"
        LLM["UnifiedLLM\n5-provider fallback chain"]
        CB["Circuit Breaker\nper-service"]
        MEM["Agent Memory\n2-tier cache"]
        EB["Event Bus\nAsync pub/sub"]
        LOCK["Distributed Lock\nRedis"]
        IDEM["Idempotency Store\nRedis"]
        MRP["Model Router\nComplexity-aware"]
        FF["Feature Flags\nGradual rollout"]
    end

    subgraph "AI Agents"
        RA["Resume Agent\nRAG + PDF"]
        CLA["Cover Letter Agent"]
        IA["Interview Agent\nSTAR + Tech Qs"]
        CA["Company Agent\nCulture Intel"]
        TA["Tracker Agent\nCRM"]
        NA["Network Agent\nLinkedIn X-Ray"]
    end

    subgraph "Services"
        RAG["RAG Service\npgvector + Gemini Embed"]
        LIVE["Live Applier\nbrowser-use + HITL"]
        STEP["Step Planner\nLLM intent routing"]
        SAL["Salary Service\nAI battle negotiation"]
    end

    subgraph "Async Worker"
        CEL["Celery\nRedis broker"]
    end

    subgraph "Storage"
        SUP["Supabase PostgreSQL\n+ pgvector + RLS"]
        RED["Redis\nLocks/Cache/Queue"]
        STOR["Supabase Storage\nPDFs"]
    end

    UI -->|HTTP + WS| MW
    MW --> REST
    MW --> WS
    REST --> IDEM
    IDEM --> PG
    PG --> N1 --> N2 --> N3
    N3 --> N4 & N5
    N4 & N5 --> N6
    N1 -.-> EB
    N4 --> RA --> RAG --> SUP
    N6 --> LIVE --> WS
    N6 --> CEL
    LLM --> CB
    MEM --> SUP
    LOCK --> RED
```

**Key insight:** Every layer has a fallback. Every failure is isolated. The pipeline keeps running even when individual providers die.

---

## 2️⃣ The Middleware Onion

Order is everything. Wrong order = security holes or wasted CPU.

```mermaid
flowchart LR
    REQ["Incoming Request"]
    REQ --> C["① CORS\nHeaders for browsers"]
    C --> S["② Request Size Limit\n10 MB cap — reject before logging"]
    S --> H["③ Security Headers\nCSP / HSTS / X-Frame"]
    H --> L["④ Request Logger\nCorrelation ID attached"]
    L --> R["⑤ Rate Limiter\nSliding window, Redis sorted-set"]
    R --> G["⑥ Credit Guard\nQuery + token budget check"]
    G --> RH["Route Handler"]
    RH --> RES["Response OUT"]
```

> **Why sliding-window rate limiting?** Fixed-window counters allow burst attacks at window edges. Sorted sets give a *true* sliding window — 100 reqs/min means 100 per any rolling 60-second window, not reset at :00 every minute.

---

## 3️⃣ LangGraph Pipeline — DAG Execution with Typed State

Every pipeline stage is an independent **async node** reading from and writing to a shared typed `PipelineState`. Edges can be conditional. Nodes can run in parallel.

```mermaid
flowchart TD
    START(["Pipeline Start\nPOST /pipeline/start"])
    START --> SP["Step Planner\nClassify intent with LLM\n~200ms"]
    SP --> SCOUT["Scout Node\nSearch 3 ATS platforms\nCircuit breaker on SerpAPI"]
    SCOUT --> ANALYST["Analyst Node\nScore each job 0-100\nllama-70B"]
    ANALYST --> COMPANY["Company Node\nCulture + interview intel\n(if enabled)"]
    COMPANY --> PAR{{"Parallel Edge"}}
    PAR --> RESUME["Resume Node\nRAG + LaTeX PDF"]
    PAR --> COVER["Cover Letter Node\nContext-aware letter"]
    RESUME --> APPLIER["Applier Node\nBrowser automation\nHITL if stuck"]
    COVER --> APPLIER
    APPLIER --> DONE(["Pipeline Complete\nAll events streamed via WS"])

    style PAR fill:#2d6a4f,color:#fff
    style START fill:#1b4332,color:#fff
    style DONE fill:#1b4332,color:#fff
```

**Why LangGraph over vanilla LangChain chains?**
- Typed state — `PipelineState` is a Pydantic model, so type errors surface at compile time, not runtime
- Conditional edges — skip expensive nodes based on user intent
- Parallel nodes — Resume and Cover Letter run **simultaneously**, not sequentially
- Checkpointing — state can be persisted mid-pipeline for restart without rerunning completed nodes

---

## 4️⃣ The 5-Provider LLM Fallback Chain

```mermaid
flowchart TD
    CALL["LLM invoke(messages, agent_name)"]
    CALL --> BUDGET{"Budget check\nper-agent daily limit"}
    BUDGET -->|"Exhausted"| ERR1["LLMError: Budget exhausted\n402 to client"]
    BUDGET -->|"OK"| P1["Provider 1\nGroq — llama-3.1-8b-instant\nSub-200ms, cheapest"]
    P1 -->|"429 Rate limit"| BACK["Exponential backoff\n1s → 2s → 4s"]
    BACK --> P1
    P1 -->|"All retries done"| P2["Provider 2\nGroq Fallback Key"]
    P2 -->|"Fail"| P3["Provider 3\nOpenRouter — Qwen3 Coder (free)"]
    P3 -->|"Fail"| P4["Provider 4\nOpenRouter Fallback Key"]
    P4 -->|"Fail"| P5["Provider 5\nGemini 2.0 Flash"]
    P5 -->|"All fail"| ERR2["LLMError: All providers failed"]
    P1 & P2 & P3 & P4 & P5 -->|"Success"| RET["Return content string"]
```

> **Model Router** picks the tier *before* hitting the chain: 8B for fast classification, 70B for deep analysis, Gemini when vision is needed. Cost-aware from the start.

---

## 5️⃣ Circuit Breaker — Three-State Resilience

Named per-service. A failure at SerpAPI doesn't cascade to your LLM or Supabase.

```mermaid
stateDiagram-v2
    [*] --> CLOSED : System start

    CLOSED --> OPEN : failures ≥ threshold\nwithin 60s sliding window
    note right of CLOSED
        All calls pass through.
        Failure deque (maxlen=1000).
        Success rate monitored.
    end note

    OPEN --> HALF_OPEN : recovery_timeout elapsed\n(30–60s)
    note right of OPEN
        All calls fail-fast.
        Fallback function returned.
        No waiting for timeout.
    end note

    HALF_OPEN --> CLOSED : probe call succeeds
    HALF_OPEN --> OPEN : probe call fails
    note right of HALF_OPEN
        ONE probe call allowed.
        Prevents thundering herd.
    end note
```

| Service | Failure Threshold | Recovery |
|---|---|---|
| `groq` | 5 failures | 60s |
| `serpapi` | 3 failures | 30s |
| `gemini` | 3 failures | 30s |
| `supabase` | 5 failures | 60s |

---

## 6️⃣ Distributed Lock + Idempotency — Preventing Chaos at Scale

Two separate weapons against the "what if two things happen at the same time" problem.

```mermaid
flowchart LR
    subgraph "Duplicate Request Problem"
        R1["User clicks Apply twice"] --> IDEM["Idempotency Store\nRedis key: user_id:session_id\nTTL: 15 min"]
        IDEM -->|"Key exists"| DUP["Return cached response\nNo pipeline re-run"]
        IDEM -->|"New key"| PROCEED["Allow pipeline start"]
    end

    subgraph "Concurrent Session Problem"
        S1["Session A"] --> LOCK["Distributed Lock\nSET key token NX EX 30\n(atomic Redis command)"]
        S2["Session B"] --> LOCK
        LOCK -->|"Acquired"| S1X["Session A: runs pipeline"]
        LOCK -->|"Rejected"| S2X["Session B: 409 Conflict"]
    end
```

> **Why Lua for lock release?** A `GET` + `DEL` across two commands has a race condition — another process could steal the lock between them. Lua executes atomically inside Redis. *This is standard Redlock pattern implementation.*

---

## 7️⃣ Event Bus — Async Pub/Sub Without Kafka

An in-process pub/sub that decouples the entire system. Agents don't know who's listening — they just emit events.

```mermaid
flowchart TD
    P["Publisher\nawait event_bus.emit('scout:found', data)"]
    P --> MW["Middleware Pipeline\n① Log event\n② PII-redact data\n③ Prometheus counter.inc()"]
    MW --> R["Route to Handlers"]
    R --> H1["Exact: 'scout:found'\n→ WebSocket broadcaster"]
    R --> H2["Wildcard: 'scout:*'\n→ Metrics recorder"]
    R --> H3["Global: '*'\n→ Audit logger"]
    H1 -. "Exception" .-> ISO["Error isolated\nOther handlers still run"]

    style ISO fill:#c1121f,color:#fff
```

> **No Kafka needed** at single-server scale. Zero serialization overhead. Handler crashes are isolated — one broken subscriber can't take down the pipeline.

---

## 8️⃣ RAG Service — Grounded AI, No Hallucination

```mermaid
flowchart LR
    subgraph "Indexing (on profile save)"
        TXT["Resume + Profile Text"] --> SPLIT["Chunker\n1000 chars, 200 overlap"]
        SPLIT --> EMBED["Gemini text-embedding-004\n768-dim vectors"]
        EMBED --> VDB["Supabase pgvector\nivfflat index"]
    end

    subgraph "Query (on resume generation)"
        Q["Job Requirements"] --> QE["Embed query\n768-dim vector"]
        QE --> CS["Cosine similarity search\nmatch_documents() RPC"]
        CS --> TOP["Top-K chunks\n(most relevant experience)"]
        TOP --> LLM["LLM Prompt\n= job requirements + real experience"]
        LLM --> OUT["Tailored resume content\ngrounded in truth"]
    end

    VDB --> CS
```

> **Why 1000-char chunks with 200 overlap?** Fits multiple chunks in a 4K context window. Overlap prevents important content from being split at chunk boundaries — a skill at end of chunk A, its description at start of chunk B, would otherwise be lost.

---

## 9️⃣ Human-in-the-Loop (HITL) — Real-Time WebSocket Bridge

The browser automation agent can pause mid-form-fill and ask the user a question. The answer travels back through WebSocket → Future → browser agent. All in real time.

```mermaid
sequenceDiagram
    participant Browser as User Browser
    participant WS as WebSocket Manager
    participant Agent as Applier Agent (browser-use)
    participant Future as asyncio.Future

    Agent->>Agent: Encounters CAPTCHA
    Agent->>WS: emit HITL_REQUEST\n{question: "Solve this captcha?"}
    WS->>Browser: Push event to UI overlay
    Browser->>WS: WS message: hitl_response\n{answer: "..."}
    WS->>Future: future.set_result(answer)
    Future-->>Agent: await unblocks
    Agent->>Agent: Continue form fill with answer
    Agent->>WS: emit APPLIER_COMPLETE
```

> **Why asyncio.Future instead of polling?** No wasted CPU in a loop. The coroutine sleeps until the user responds. The Future is the exact primitive for "wait for an external event" in Python asyncio.

---

## 🔟 Observability Stack — You Can't Fix What You Can't See

```mermaid
flowchart LR
    APP["Application Code"] --> SLOG["Structured Logger\nJSON + correlation ID\nPII-redacted fields"]
    APP --> PROM["Prometheus Metrics\n/metrics endpoint\npipeline_runs / latency / tokens"]
    APP --> OTEL["OpenTelemetry\nLangChainInstrumentor\nAuto-spans every LLM call"]
    SLOG --> DASH["Log aggregator\nDatadog / CloudWatch"]
    PROM --> GRAF["Grafana Dashboard"]
    OTEL --> PHOENIX["Arize Phoenix\nLLM trace viewer"]
```

> **One line. Entire codebase.** `LangChainInstrumentor().instrument()` — no manual span code needed anywhere. Every LLM call, chain step, and agent execution gets a trace automatically.

---

## 🔑 System Design Concepts Used — At a Glance

| Concept | Pattern | Where Used |
|---|---|---|
| **DAG Orchestration** | LangGraph StateGraph | Pipeline execution |
| **5-Provider Fallback** | Circuit Breaker + Retry | UnifiedLLM |
| **Pub/Sub Event Bus** | In-process Mediator | Agent communication |
| **Distributed Lock** | Redis SET NX + Lua | Concurrent session protection |
| **Idempotency** | Redis key + TTL | Duplicate request prevention |
| **RAG** | Embedding + Vector Search | Resume/Cover Letter grounding |
| **HITL** | WebSocket + asyncio.Future | Browser automation pausing |
| **Sliding Window Rate Limit** | Redis Sorted Sets | API protection |
| **DI Container** | Service Locator (Singleton/Factory) | Dependency management |
| **Feature Flags** | SHA256 deterministic bucketing | Gradual rollout |
| **Model Routing** | Complexity-aware selector | Cost optimization |
| **PII Redaction** | Regex + confidence threshold | GDPR compliance |
| **2-tier Agent Memory** | Redis (hot) + Supabase (cold) | Personalization |
| **Async Task Queue** | Celery + Redis | Browser process isolation |
| **Graceful Degradation** | Try/except at every boundary | Memory, guardrails, locks |
| **OpenTelemetry Tracing** | Auto-instrumentation | LLM observability |
| **Structured Logging** | ContextVar async propagation | Correlation across async tree |

---

## 🧮 Numbers That Matter

| Metric | Value |
|---|---|
| LLM providers in fallback chain | 5 |
| Middleware layers before route handler | 6 |
| Pipeline nodes (async) | 6 |
| Parallel nodes (Resume + Cover Letter) | 2 |
| Vector embedding dimensions | 768 |
| Circuit breaker recovery window | 30–60s |
| Idempotency TTL | 15 minutes |
| Rate limit window | 60s sliding |
| Daily credit budget (queries) | 200 per user |
| Max applier steps (browser agent) | 30 |

---

*Day 1 → Project Overview · Day 2 → AI Architecture · **Day 3 → System Design** · Day 4 → Deployment*
