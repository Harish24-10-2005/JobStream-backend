# JobAI Backend — Full Technical Reference

> **Production-grade AI career assistant backend** — FastAPI · LangGraph · Multi-provider LLM · RAG · WebSocket · Celery · Supabase · Redis

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Repository Structure](#2-repository-structure)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Request Lifecycle and Middleware Stack](#4-request-lifecycle-and-middleware-stack)
5. [API Layer — Routes and Schemas](#5-api-layer--routes-and-schemas)
6. [WebSocket Real-Time Layer](#6-websocket-real-time-layer)
7. [Feature Deep Dives](#7-feature-deep-dives)
8. [Core Infrastructure](#8-core-infrastructure)
9. [Background Task System — Celery](#9-background-task-system--celery)
10. [Database Design](#10-database-design)
11. [Non-Functional Requirements (Production)](#11-non-functional-requirements-production)
12. [Security Model](#12-security-model)
13. [Observability Stack](#13-observability-stack)
14. [Configuration Reference](#14-configuration-reference)
15. [Local Development and Running](#15-local-development-and-running)
16. [Testing Strategy](#16-testing-strategy)
17. [Deployment — Docker and Kubernetes](#17-deployment--docker-and-kubernetes)
18. [Why Each Technology Was Chosen](#18-why-each-technology-was-chosen)

---
