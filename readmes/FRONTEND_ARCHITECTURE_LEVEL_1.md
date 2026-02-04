# 🎨 Frontend Architecture - Level 1: Authentication & Foundation

**Production-Grade Next.js 15+ Frontend Architecture**  
**Phase:** Level 1 - Authentication, WebSocket, User Management  
**Target:** February 2026  
**Status:** 📋 Planning Phase

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Backend Analysis](#backend-analysis)
3. [Frontend Tech Stack](#frontend-tech-stack)
4. [Level 1 Scope](#level-1-scope)
5. [Architecture Design](#architecture-design)
6. [Authentication System](#authentication-system)
7. [WebSocket Integration](#websocket-integration)
8. [State Management](#state-management)
9. [API Client Architecture](#api-client-architecture)
10. [UI/UX Design System](#uiux-design-system)
11. [Folder Structure](#folder-structure)
12. [Implementation Roadmap](#implementation-roadmap)
13. [Security Best Practices](#security-best-practices)
14. [Performance Optimization](#performance-optimization)
15. [Testing Strategy](#testing-strategy)

---

## 🎯 Executive Summary

### Mission
Build a production-grade **Next.js 15+ frontend** that seamlessly integrates with the existing FastAPI backend, focusing on **authentication, real-time WebSocket communication, and user profile management** as the foundational layer (Level 1).

### Key Objectives

| Objective | Description | Priority |
|-----------|-------------|----------|
| **Supabase Auth Integration** | OAuth (Google, GitHub) + Email/Password signup | 🔴 Critical |
| **JWT Token Management** | Secure token storage, refresh, and validation | 🔴 Critical |
| **WebSocket Client** | Real-time event streaming from backend | 🔴 Critical |
| **User Profile Management** | Onboarding flow, profile CRUD operations | 🟡 High |
| **Type-Safe API Client** | Axios/fetch wrapper with TypeScript | 🟡 High |
| **Responsive Design** | Mobile-first, accessible UI components | 🟢 Medium |

### Success Metrics
- ✅ 100% TypeScript coverage
- ✅ < 3s initial page load (Lighthouse score > 90)
- ✅ < 100ms WebSocket latency
- ✅ Zero auth vulnerabilities (JWT best practices)
- ✅ 100% API endpoint coverage (all backend routes typed)

---

## 🔍 Backend Analysis

### Backend Capabilities (What Frontend Must Support)

#### 1. **Authentication System** (`backend/src/core/auth.py`)

```python
# Backend Auth Model
class AuthUser:
    id: str          # Supabase UUID
    email: str
    role: str = "authenticated"

# JWT Verification
- Supports HS256 (symmetric) and ES256 (asymmetric)
- Token validation via Supabase JWT Secret
- JWKS caching (1 hour TTL)
- Rate limiting (60 req/min per user)

# Dependencies
- get_current_user(): Required for protected routes
- verify_token(): For WebSocket authentication
- rate_limit_check(): Prevents abuse
```

**Frontend Requirements:**
- Store JWT token from Supabase Auth
- Send token in `Authorization: Bearer <token>` header
- Handle 401 (expired token) → Refresh token flow
- Handle 429 (rate limit) → Show "Too many requests" UI

---

#### 2. **User Profile System** (`backend/src/api/routes/user.py`)

**Available Endpoints:**

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/user/profile` | GET | ✅ | Get user profile |
| `/api/user/profile` | POST | ✅ | Create profile (onboarding) |
| `/api/user/profile` | PUT | ✅ | Update profile |
| `/api/user/profile/completion` | GET | ✅ | Get onboarding progress |
| `/api/user/education` | POST | ✅ | Add education |
| `/api/user/experience` | POST | ✅ | Add work experience |
| `/api/user/projects` | POST | ✅ | Add project |
| `/api/user/resume/upload` | POST | ✅ | Upload resume PDF |
| `/api/user/resumes` | GET | ✅ | List all resumes |
| `/api/user/resume/primary` | GET | ✅ | Get primary resume |

**Profile Data Model:**
```typescript
interface UserProfile {
  personal_information: {
    first_name: string;
    last_name: string;
    full_name: string;
    email: string;
    phone: string;
    location: { city: string; country: string; address: string };
    urls: { linkedin?: string; github?: string; portfolio?: string };
  };
  education: Education[];
  experience: Experience[];
  projects: Project[];
  skills: Record<string, string[]>;  // { "languages": ["Python", "TypeScript"] }
  files: { resume: string };
  application_preferences?: {
    expected_salary: string;
    notice_period: string;
    work_authorization: string;
    relocation: string;
    employment_type: string[];
  };
  behavioral_questions?: Record<string, string>;
}
```

---

#### 3. **WebSocket System** (`backend/src/api/websocket.py`)

**Connection URL:**
```
ws://localhost:8000/ws/{session_id}?token={jwt_token}
```

**Event Types (90+ events):**
```typescript
enum EventType {
  // Connection
  CONNECTED = "connected",
  DISCONNECTED = "disconnected",
  
  // Pipeline
  PIPELINE_START = "pipeline_start",
  PIPELINE_COMPLETE = "pipeline_complete",
  PIPELINE_ERROR = "pipeline_error",
  
  // Scout Agent
  SCOUT_START = "scout_start",
  SCOUT_SEARCHING = "scout_searching",
  SCOUT_FOUND = "scout_found",
  SCOUT_COMPLETE = "scout_complete",
  
  // Analyst Agent
  ANALYST_START = "analyst_start",
  ANALYST_FETCHING = "analyst_fetching",
  ANALYST_RESULT = "analyst_result",
  
  // Applier Agent (Browser Automation)
  APPLIER_START = "applier_start",
  APPLIER_NAVIGATE = "applier_navigate",
  APPLIER_CLICK = "applier_click",
  APPLIER_TYPE = "applier_type",
  APPLIER_UPLOAD = "applier_upload",
  APPLIER_COMPLETE = "applier_complete",
  
  // HITL (Human-in-the-Loop)
  HITL_REQUEST = "hitl_request",
  HITL_RESPONSE = "hitl_response",
  HITL_TIMEOUT = "hitl_timeout",
  
  // Browser Streaming
  BROWSER_SCREENSHOT = "browser_screenshot",  // Base64 JPEG, 5 FPS
  
  // Resume/Cover Letter
  RESUME_START = "resume_start",
  RESUME_COMPLETE = "resume_complete",
  COVER_LETTER_START = "cover_letter_start",
  COVER_LETTER_COMPLETE = "cover_letter_complete",
  
  // ... 60+ more event types
}
```

**Message Protocols:**

**Client → Server:**
```json
// Start Pipeline
{
  "type": "start_pipeline",
  "data": {
    "query": "Python Developer",
    "location": "Remote",
    "auto_apply": true,
    "use_resume_tailoring": true,
    "use_cover_letter": true
  }
}

// HITL Response
{
  "type": "hitl_response",
  "data": {
    "hitl_id": "hitl_1234567890.123",
    "response": "yes"
  }
}

// Ping
{ "type": "ping" }
```

**Server → Client:**
```json
// Agent Event
{
  "type": "scout_found",
  "agent": "scout",
  "message": "Found 47 job listings",
  "data": { "count": 47, "urls": ["..."] },
  "timestamp": "2026-02-02T10:30:45.123Z"
}

// HITL Request
{
  "type": "hitl_request",
  "agent": "applier",
  "message": "Confirm phone number: (123) 456-7890?",
  "data": {
    "hitl_id": "hitl_1234567890.123",
    "question": "Is this your phone number?",
    "context": "LinkedIn Easy Apply form"
  }
}

// Browser Screenshot
{
  "type": "browser_screenshot",
  "agent": "applier",
  "message": "Browser screenshot",
  "data": {
    "screenshot": "/9j/4AAQSkZJRgABAQAAAQABAAD...",  // Base64 JPEG
    "format": "jpeg"
  }
}
```

---

#### 4. **Other API Routes** (For Future Levels)

| Route | Purpose | Level |
|-------|---------|-------|
| `/api/jobs/*` | Job search, analyze, apply | Level 2 |
| `/api/pipeline/*` | Pipeline control, status | Level 2 |
| `/api/resume/*` | Resume tailoring, templates | Level 3 |
| `/api/cover_letter/*` | Cover letter generation | Level 3 |
| `/api/company/*` | Company research | Level 3 |
| `/api/network/*` | LinkedIn networking | Level 4 |
| `/api/interview/*` | Interview prep | Level 4 |
| `/api/salary/*` | Salary negotiation | Level 5 |
| `/api/chat/*` | AI chat assistant | Level 5 |

---

## 🛠️ Frontend Tech Stack

### Core Framework

```json
{
  "framework": "Next.js 15.1.4",
  "react": "19.0.0",
  "typescript": "5.x",
  "reason": "App Router, Server Components, Streaming, Turbopack"
}
```

### Authentication

```json
{
  "provider": "@supabase/supabase-js 2.x",
  "auth_ui": "@supabase/auth-ui-react",
  "features": [
    "OAuth (Google, GitHub)",
    "Email/Password",
    "JWT token management",
    "Automatic token refresh"
  ]
}
```

### State Management

```json
{
  "global_state": "Zustand 4.x",
  "server_state": "@tanstack/react-query 5.x",
  "forms": "react-hook-form 7.x + zod",
  "reason": "Lightweight, TypeScript-first, easy testing"
}
```

### WebSocket Client

```json
{
  "library": "native WebSocket API",
  "wrapper": "custom useWebSocket hook",
  "features": [
    "Auto-reconnect with exponential backoff",
    "Event history buffer (last 50 events)",
    "Typed message protocols"
  ]
}
```

### UI Components

```json
{
  "component_library": "shadcn/ui (Radix UI + Tailwind)",
  "styling": "Tailwind CSS 3.x",
  "icons": "lucide-react",
  "animations": "framer-motion 11.x"
}
```

### API Client

```json
{
  "http_client": "axios 1.x",
  "wrapper": "custom ApiClient class",
  "features": [
    "JWT interceptor",
    "Retry logic (exponential backoff)",
    "TypeScript response types",
    "Error handling"
  ]
}
```

### Development Tools

```json
{
  "linting": "ESLint 9.x + TypeScript ESLint",
  "formatting": "Prettier 3.x",
  "testing": "Vitest + React Testing Library",
  "e2e": "Playwright",
  "api_mocking": "MSW (Mock Service Worker)"
}
```

### Deployment

```json
{
  "platform": "Vercel",
  "env_management": ".env.local + Vercel Environment Variables",
  "cdn": "Vercel Edge Network",
  "analytics": "Vercel Analytics + Web Vitals"
}
```

---

## 📐 Level 1 Scope

### What We're Building in Level 1

```
┌─────────────────────────────────────────────────────────────────┐
│                       LEVEL 1 FEATURES                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1️⃣  AUTHENTICATION & AUTHORIZATION                            │
│      ✅ Login Page (Email/Password + OAuth)                     │
│      ✅ Signup Page with Email Verification                     │
│      ✅ Password Reset Flow                                     │
│      ✅ JWT Token Management (store, refresh, expire)           │
│      ✅ Protected Routes (middleware)                           │
│      ✅ Auth Context Provider                                   │
│                                                                 │
│  2️⃣  USER PROFILE & ONBOARDING                                 │
│      ✅ Multi-Step Onboarding Form                              │
│         - Step 1: Personal Info                                 │
│         - Step 2: Education                                     │
│         - Step 3: Work Experience                               │
│         - Step 4: Projects                                      │
│         - Step 5: Skills                                        │
│         - Step 6: Resume Upload                                 │
│      ✅ Profile Dashboard                                       │
│      ✅ Profile Edit Page                                       │
│      ✅ Resume Management (upload, view, delete)                │
│                                                                 │
│  3️⃣  WEBSOCKET INTEGRATION                                     │
│      ✅ WebSocket Client Hook (useWebSocket)                    │
│      ✅ Connection Manager                                      │
│      ✅ Event Listener System                                   │
│      ✅ Auto-Reconnect with Backoff                             │
│      ✅ Event History Buffer                                    │
│      ✅ HITL Modal Component                                    │
│                                                                 │
│  4️⃣  API CLIENT LAYER                                          │
│      ✅ Axios Instance with Interceptors                        │
│      ✅ JWT Auto-Injection                                      │
│      ✅ Error Handling & Retry Logic                            │
│      ✅ TypeScript Response Types                               │
│      ✅ API Service Modules (auth, user, profile)               │
│                                                                 │
│  5️⃣  UI/UX FOUNDATION                                          │
│      ✅ Design System Setup (shadcn/ui)                         │
│      ✅ Global Styles (Tailwind config)                         │
│      ✅ Responsive Layout Components                            │
│      ✅ Loading States & Skeletons                              │
│      ✅ Error Boundaries                                        │
│      ✅ Toast Notifications                                     │
│                                                                 │
│  6️⃣  STATE MANAGEMENT                                          │
│      ✅ Zustand Store (auth, user, websocket)                   │
│      ✅ React Query Setup (API cache)                           │
│      ✅ Form State (react-hook-form + zod)                      │
│                                                                 │
│  7️⃣  ROUTING & NAVIGATION                                      │
│      ✅ App Router Setup                                        │
│      ✅ Protected Route Middleware                              │
│      ✅ Public vs Private Pages                                 │
│      ✅ Navigation Bar                                          │
│      ✅ Sidebar (for dashboard)                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Out of Scope (Future Levels)

❌ Job search interface (Level 2)  
❌ Pipeline dashboard (Level 2)  
❌ Resume tailoring UI (Level 3)  
❌ Cover letter generation UI (Level 3)  
❌ Company research UI (Level 3)  
❌ Networking features (Level 4)  
❌ Interview prep (Level 4)  
❌ Salary negotiation (Level 5)  
❌ AI chat assistant (Level 5)

---

## 🏗️ Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER BROWSER                                 │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                 Next.js 15 App                            │  │
│  │                                                           │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │         Presentation Layer (Pages/Components)       │  │  │
│  │  │  - Login, Signup, Dashboard, Profile, Onboarding   │  │  │
│  │  └─────────────────┬──────────────────────────────────┘  │  │
│  │                    │                                      │  │
│  │  ┌─────────────────▼──────────────────────────────────┐  │  │
│  │  │           State Management Layer                    │  │  │
│  │  │  - Zustand (auth, user, websocket)                  │  │  │
│  │  │  - React Query (API cache)                          │  │  │
│  │  │  - React Hook Form (forms)                          │  │  │
│  │  └─────────────────┬──────────────────────────────────┘  │  │
│  │                    │                                      │  │
│  │  ┌─────────────────▼──────────────────────────────────┐  │  │
│  │  │           Service Layer                             │  │  │
│  │  │  - API Client (Axios)                               │  │  │
│  │  │  - WebSocket Client                                 │  │  │
│  │  │  - Supabase Client                                  │  │  │
│  │  └─────────────────┬──────────────────────────────────┘  │  │
│  │                    │                                      │  │
│  └────────────────────┼──────────────────────────────────────┘  │
│                       │                                         │
└───────────────────────┼─────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Supabase   │ │   FastAPI    │ │   FastAPI    │
│     Auth     │ │   REST API   │ │  WebSocket   │
│              │ │              │ │              │
│ OAuth Tokens │ │ JWT Verify   │ │ Real-time    │
│ User Mgmt    │ │ User Profile │ │ Events       │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    1. PRESENTATION LAYER                    │
│  - Pages (App Router)                                       │
│  - Components (shadcn/ui + custom)                          │
│  - Layouts (RootLayout, DashboardLayout)                    │
│  - Middleware (route protection)                            │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    2. BUSINESS LOGIC LAYER                  │
│  - Custom Hooks (useAuth, useWebSocket, useProfile)         │
│  - Utils (formatters, validators)                           │
│  - Constants (API URLs, event types)                        │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    3. STATE MANAGEMENT LAYER                │
│  - Zustand Stores (global state)                            │
│  - React Query (server state cache)                         │
│  - React Hook Form (form state)                             │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    4. DATA ACCESS LAYER                     │
│  - API Client (Axios wrapper)                               │
│  - WebSocket Client (native WebSocket wrapper)              │
│  - Supabase Client (@supabase/supabase-js)                  │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    5. EXTERNAL SERVICES                     │
│  - Supabase Auth (JWT tokens)                               │
│  - FastAPI Backend (REST + WebSocket)                       │
│  - Vercel Analytics                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 Authentication System

### Authentication Flow

```
┌────────────────────────────────────────────────────────────────┐
│                     LOGIN FLOW                                 │
└────────────────────────────────────────────────────────────────┘

1. User visits /login
   ↓
2. User enters email + password (or clicks "Sign in with Google")
   ↓
3. Frontend → Supabase Auth API
   ↓
4. Supabase validates credentials
   ↓
5. Supabase returns JWT access token + refresh token
   ↓
6. Frontend stores tokens:
   - Access Token: Memory (Zustand store)
   - Refresh Token: HttpOnly cookie (Supabase manages)
   ↓
7. Frontend checks if user has profile:
   - GET /api/user/profile (with JWT token)
   ↓
8. If profile exists → Redirect to /dashboard
   If no profile → Redirect to /onboarding
```

### Signup Flow

```
┌────────────────────────────────────────────────────────────────┐
│                     SIGNUP FLOW                                │
└────────────────────────────────────────────────────────────────┘

1. User visits /signup
   ↓
2. User enters email + password
   ↓
3. Frontend → Supabase Auth API (signUp)
   ↓
4. Supabase sends verification email
   ↓
5. User clicks link in email
   ↓
6. Supabase confirms email
   ↓
7. User logs in → JWT tokens issued
   ↓
8. Frontend redirects to /onboarding (no profile yet)
```

### Token Management

```typescript
// Token Storage Strategy
┌─────────────────────────────────────────────────────────────┐
│  Access Token (JWT)                                         │
│  - Storage: Zustand store (in-memory)                       │
│  - Lifetime: 1 hour                                         │
│  - Usage: Authorization header for API requests             │
│  - Security: Never stored in localStorage                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Refresh Token                                              │
│  - Storage: HttpOnly cookie (Supabase managed)              │
│  - Lifetime: 7 days                                         │
│  - Usage: Automatic token refresh                           │
│  - Security: Cannot be accessed by JavaScript               │
└─────────────────────────────────────────────────────────────┘

// Token Refresh Flow
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│  1. API request returns 401 (token expired)                    │
│     ↓                                                          │
│  2. Axios interceptor catches 401                              │
│     ↓                                                          │
│  3. Call supabase.auth.refreshSession()                        │
│     ↓                                                          │
│  4. Supabase uses refresh token → new access token             │
│     ↓                                                          │
│  5. Update Zustand store with new token                        │
│     ↓                                                          │
│  6. Retry original request with new token                      │
│     ↓                                                          │
│  7. If refresh fails → Redirect to /login                      │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

#### 1. **Supabase Client Setup**

```typescript
// lib/supabase/client.ts
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true
  }
});

// Helper to get current session
export async function getSession() {
  const { data: { session } } = await supabase.auth.getSession();
  return session;
}

// Helper to get access token
export async function getAccessToken() {
  const session = await getSession();
  return session?.access_token || null;
}
```

#### 2. **Auth Store (Zustand)**

```typescript
// store/auth.store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { supabase } from '@/lib/supabase/client';
import type { User, Session } from '@supabase/supabase-js';

interface AuthState {
  user: User | null;
  session: Session | null;
  loading: boolean;
  initialized: boolean;
  
  // Actions
  setUser: (user: User | null) => void;
  setSession: (session: Session | null) => void;
  login: (email: string, password: string) => Promise<{ error?: string }>;
  signup: (email: string, password: string) => Promise<{ error?: string }>;
  logout: () => Promise<void>;
  initialize: () => Promise<void>;
  refreshSession: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      session: null,
      loading: false,
      initialized: false,
      
      setUser: (user) => set({ user }),
      setSession: (session) => set({ session, user: session?.user || null }),
      
      initialize: async () => {
        set({ loading: true });
        try {
          const { data: { session } } = await supabase.auth.getSession();
          set({ session, user: session?.user || null, initialized: true });
          
          // Listen for auth changes
          supabase.auth.onAuthStateChange((_event, session) => {
            set({ session, user: session?.user || null });
          });
        } catch (error) {
          console.error('Auth initialization failed:', error);
        } finally {
          set({ loading: false });
        }
      },
      
      login: async (email, password) => {
        set({ loading: true });
        try {
          const { data, error } = await supabase.auth.signInWithPassword({
            email,
            password
          });
          
          if (error) return { error: error.message };
          
          set({ session: data.session, user: data.user });
          return {};
        } catch (error: any) {
          return { error: error.message };
        } finally {
          set({ loading: false });
        }
      },
      
      signup: async (email, password) => {
        set({ loading: true });
        try {
          const { error } = await supabase.auth.signUp({
            email,
            password,
            options: {
              emailRedirectTo: `${window.location.origin}/auth/callback`
            }
          });
          
          if (error) return { error: error.message };
          return {};
        } catch (error: any) {
          return { error: error.message };
        } finally {
          set({ loading: false });
        }
      },
      
      logout: async () => {
        await supabase.auth.signOut();
        set({ user: null, session: null });
      },
      
      refreshSession: async () => {
        const { data: { session } } = await supabase.auth.refreshSession();
        set({ session, user: session?.user || null });
      }
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ 
        // Don't persist session/user (managed by Supabase)
        initialized: state.initialized 
      })
    }
  )
);
```

#### 3. **Auth Context Provider**

```typescript
// providers/auth-provider.tsx
'use client';

import { useEffect } from 'react';
import { useAuthStore } from '@/store/auth.store';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const initialize = useAuthStore((state) => state.initialize);
  const initialized = useAuthStore((state) => state.initialized);
  
  useEffect(() => {
    if (!initialized) {
      initialize();
    }
  }, [initialized, initialize]);
  
  return <>{children}</>;
}
```

#### 4. **Protected Route Middleware**

```typescript
// middleware.ts
import { createMiddlewareClient } from '@supabase/auth-helpers-nextjs';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function middleware(req: NextRequest) {
  const res = NextResponse.next();
  const supabase = createMiddlewareClient({ req, res });
  
  const { data: { session } } = await supabase.auth.getSession();
  
  const isAuthPage = req.nextUrl.pathname.startsWith('/login') || 
                     req.nextUrl.pathname.startsWith('/signup');
  const isProtectedPage = req.nextUrl.pathname.startsWith('/dashboard') ||
                          req.nextUrl.pathname.startsWith('/profile') ||
                          req.nextUrl.pathname.startsWith('/onboarding');
  
  // Redirect authenticated users away from auth pages
  if (session && isAuthPage) {
    return NextResponse.redirect(new URL('/dashboard', req.url));
  }
  
  // Redirect unauthenticated users to login
  if (!session && isProtectedPage) {
    const redirectUrl = new URL('/login', req.url);
    redirectUrl.searchParams.set('redirect', req.nextUrl.pathname);
    return NextResponse.redirect(redirectUrl);
  }
  
  return res;
}

export const config = {
  matcher: ['/dashboard/:path*', '/profile/:path*', '/onboarding/:path*', '/login', '/signup']
};
```

#### 5. **Login Page Component**

```typescript
// app/login/page.tsx
'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/store/auth.store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from '@/components/ui/use-toast';
import { supabase } from '@/lib/supabase/client';

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectUrl = searchParams.get('redirect') || '/dashboard';
  
  const login = useAuthStore((state) => state.login);
  const loading = useAuthStore((state) => state.loading);
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const { error } = await login(email, password);
    
    if (error) {
      toast({ title: 'Login failed', description: error, variant: 'destructive' });
      return;
    }
    
    toast({ title: 'Login successful', description: 'Redirecting...' });
    router.push(redirectUrl);
  };
  
  const handleGoogleLogin = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback?redirect=${redirectUrl}`
      }
    });
    
    if (error) {
      toast({ title: 'OAuth failed', description: error.message, variant: 'destructive' });
    }
  };
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div>
          <h2 className="text-3xl font-bold text-center">Sign in to JobStream</h2>
        </div>
        
        <form onSubmit={handleLogin} className="space-y-6">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign in'}
          </Button>
        </form>
        
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-white text-gray-500">Or continue with</span>
          </div>
        </div>
        
        <Button variant="outline" className="w-full" onClick={handleGoogleLogin}>
          Sign in with Google
        </Button>
        
        <p className="text-center text-sm text-gray-600">
          Don't have an account?{' '}
          <a href="/signup" className="text-blue-600 hover:underline">
            Sign up
          </a>
        </p>
      </div>
    </div>
  );
}
```

---

## 🔌 WebSocket Integration

### WebSocket Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND WEBSOCKET CLIENT                    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               useWebSocket Hook                           │  │
│  │  - Connection management                                  │  │
│  │  - Auto-reconnect with exponential backoff                │  │
│  │  - Event listeners registry                               │  │
│  │  - Message queue (for offline messages)                   │  │
│  │  - Event history buffer (last 50 events)                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                           │ WebSocket Protocol                  │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              BACKEND WEBSOCKET SERVER (FastAPI)                 │
│                                                                 │
│  Connection URL: ws://localhost:8000/ws/{session_id}?token=JWT  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │          ConnectionManager (Singleton)                    │  │
│  │  - Active connections (user_id → WebSocket)               │  │
│  │  - Event history (last 50 per session)                    │  │
│  │  - HITL callbacks (pending responses)                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

#### 1. **WebSocket Hook**

```typescript
// hooks/useWebSocket.ts
import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuthStore } from '@/store/auth.store';
import { toast } from '@/components/ui/use-toast';

export interface AgentEvent {
  type: string;
  agent: string;
  message: string;
  data: Record<string, any>;
  timestamp: string;
}

interface UseWebSocketOptions {
  sessionId: string;
  onEvent?: (event: AgentEvent) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  autoReconnect?: boolean;
  maxReconnectAttempts?: number;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const {
    sessionId,
    onEvent,
    onConnect,
    onDisconnect,
    onError,
    autoReconnect = true,
    maxReconnectAttempts = 5
  } = options;
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  
  const session = useAuthStore((state) => state.session);
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  
  const connect = useCallback(() => {
    if (!session?.access_token) {
      console.error('No access token available');
      return;
    }
    
    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL}/ws/${sessionId}?token=${session.access_token}`;
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
      reconnectAttempts.current = 0;
      onConnect?.();
    };
    
    ws.onmessage = (event) => {
      try {
        const data: AgentEvent = JSON.parse(event.data);
        setEvents((prev) => [...prev, data].slice(-50)); // Keep last 50 events
        onEvent?.(data);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };
    
    ws.onclose = (event) => {
      console.log('WebSocket disconnected', event.code, event.reason);
      setConnected(false);
      wsRef.current = null;
      onDisconnect?.();
      
      // Auto-reconnect with exponential backoff
      if (autoReconnect && reconnectAttempts.current < maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
        console.log(`Reconnecting in ${delay}ms...`);
        
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectAttempts.current++;
          connect();
        }, delay);
      } else if (reconnectAttempts.current >= maxReconnectAttempts) {
        toast({
          title: 'Connection failed',
          description: 'Unable to connect to server. Please refresh the page.',
          variant: 'destructive'
        });
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      onError?.(error);
    };
    
    wsRef.current = ws;
  }, [sessionId, session, onConnect, onDisconnect, onEvent, onError, autoReconnect, maxReconnectAttempts]);
  
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);
  
  const sendMessage = useCallback((type: string, data: Record<string, any>) => {
    if (wsRef.current && connected) {
      wsRef.current.send(JSON.stringify({ type, data }));
    } else {
      console.warn('WebSocket not connected, message not sent');
    }
  }, [connected]);
  
  // Initialize connection
  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);
  
  return {
    connected,
    events,
    sendMessage,
    disconnect,
    reconnect: connect
  };
}
```

#### 2. **WebSocket Store (Zustand)**

```typescript
// store/websocket.store.ts
import { create } from 'zustand';
import type { AgentEvent } from '@/hooks/useWebSocket';

interface WebSocketState {
  connected: boolean;
  events: AgentEvent[];
  hitlQueue: Array<{ hitl_id: string; question: string; context: string }>;
  
  setConnected: (connected: boolean) => void;
  addEvent: (event: AgentEvent) => void;
  clearEvents: () => void;
  addHITLRequest: (hitl_id: string, question: string, context: string) => void;
  removeHITLRequest: (hitl_id: string) => void;
}

export const useWebSocketStore = create<WebSocketState>((set) => ({
  connected: false,
  events: [],
  hitlQueue: [],
  
  setConnected: (connected) => set({ connected }),
  
  addEvent: (event) => 
    set((state) => ({ 
      events: [...state.events, event].slice(-50) // Keep last 50 events
    })),
  
  clearEvents: () => set({ events: [] }),
  
  addHITLRequest: (hitl_id, question, context) =>
    set((state) => ({
      hitlQueue: [...state.hitlQueue, { hitl_id, question, context }]
    })),
  
  removeHITLRequest: (hitl_id) =>
    set((state) => ({
      hitlQueue: state.hitlQueue.filter((req) => req.hitl_id !== hitl_id)
    }))
}));
```

#### 3. **HITL Modal Component**

```typescript
// components/hitl-modal.tsx
'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface HITLModalProps {
  open: boolean;
  hitlId: string;
  question: string;
  context: string;
  onResponse: (hitlId: string, response: string) => void;
  onCancel: () => void;
}

export function HITLModal({
  open,
  hitlId,
  question,
  context,
  onResponse,
  onCancel
}: HITLModalProps) {
  const [response, setResponse] = useState('');
  
  const handleSubmit = () => {
    onResponse(hitlId, response);
    setResponse('');
  };
  
  return (
    <Dialog open={open} onOpenChange={onCancel}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Human Input Required</DialogTitle>
          <DialogDescription>{context}</DialogDescription>
        </DialogHeader>
        
        <div className="py-4">
          <Label htmlFor="response">{question}</Label>
          <Input
            id="response"
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            placeholder="Your answer..."
            autoFocus
          />
        </div>
        
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!response.trim()}>
            Submit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

#### 4. **Usage Example**

```typescript
// app/dashboard/page.tsx
'use client';

import { useState } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useWebSocketStore } from '@/store/websocket.store';
import { HITLModal } from '@/components/hitl-modal';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';

export default function DashboardPage() {
  const [hitlModal, setHITLModal] = useState<{
    open: boolean;
    hitl_id?: string;
    question?: string;
    context?: string;
  }>({ open: false });
  
  const { connected, sendMessage } = useWebSocket({
    sessionId: 'user-session-123',
    onEvent: (event) => {
      console.log('Received event:', event);
      
      // Handle HITL request
      if (event.type === 'hitl_request') {
        setHITLModal({
          open: true,
          hitl_id: event.data.hitl_id,
          question: event.data.question,
          context: event.data.context
        });
      }
      
      // Show toast for important events
      if (event.type === 'pipeline_complete') {
        toast({
          title: 'Pipeline Complete',
          description: event.message
        });
      }
    },
    onConnect: () => {
      toast({ title: 'Connected', description: 'WebSocket connected' });
    },
    onDisconnect: () => {
      toast({ title: 'Disconnected', description: 'WebSocket disconnected', variant: 'destructive' });
    }
  });
  
  const handleStartPipeline = () => {
    sendMessage('start_pipeline', {
      query: 'Python Developer',
      location: 'Remote',
      auto_apply: true
    });
  };
  
  const handleHITLResponse = (hitlId: string, response: string) => {
    sendMessage('hitl_response', {
      hitl_id: hitlId,
      response
    });
    setHITLModal({ open: false });
  };
  
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-4">Dashboard</h1>
      
      <div className="mb-4">
        <span className={`inline-block w-2 h-2 rounded-full mr-2 ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        {connected ? 'Connected' : 'Disconnected'}
      </div>
      
      <Button onClick={handleStartPipeline} disabled={!connected}>
        Start Job Search Pipeline
      </Button>
      
      <HITLModal
        open={hitlModal.open}
        hitlId={hitlModal.hitl_id || ''}
        question={hitlModal.question || ''}
        context={hitlModal.context || ''}
        onResponse={handleHITLResponse}
        onCancel={() => setHITLModal({ open: false })}
      />
    </div>
  );
}
```

---

## 🗂️ Folder Structure

```
frontend/
├── .next/                          # Next.js build output
├── public/                         # Static assets
│   ├── images/
│   └── favicon.ico
├── src/
│   ├── app/                        # Next.js 15 App Router
│   │   ├── (auth)/                 # Auth route group (public)
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   ├── signup/
│   │   │   │   └── page.tsx
│   │   │   ├── forgot-password/
│   │   │   │   └── page.tsx
│   │   │   └── auth/
│   │   │       └── callback/
│   │   │           └── route.ts    # OAuth callback handler
│   │   ├── (dashboard)/            # Dashboard route group (protected)
│   │   │   ├── dashboard/
│   │   │   │   └── page.tsx
│   │   │   ├── profile/
│   │   │   │   ├── page.tsx
│   │   │   │   └── edit/
│   │   │   │       └── page.tsx
│   │   │   └── layout.tsx          # Dashboard layout with sidebar
│   │   ├── onboarding/             # Onboarding flow (protected)
│   │   │   ├── page.tsx            # Step 1: Personal Info
│   │   │   ├── education/
│   │   │   │   └── page.tsx        # Step 2: Education
│   │   │   ├── experience/
│   │   │   │   └── page.tsx        # Step 3: Experience
│   │   │   ├── projects/
│   │   │   │   └── page.tsx        # Step 4: Projects
│   │   │   ├── skills/
│   │   │   │   └── page.tsx        # Step 5: Skills
│   │   │   └── resume/
│   │   │       └── page.tsx        # Step 6: Resume Upload
│   │   ├── layout.tsx              # Root layout
│   │   ├── page.tsx                # Landing page
│   │   └── globals.css             # Global styles
│   ├── components/                 # React components
│   │   ├── ui/                     # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── toast.tsx
│   │   │   └── ...
│   │   ├── auth/
│   │   │   ├── login-form.tsx
│   │   │   ├── signup-form.tsx
│   │   │   └── oauth-buttons.tsx
│   │   ├── profile/
│   │   │   ├── profile-card.tsx
│   │   │   ├── profile-form.tsx
│   │   │   └── resume-uploader.tsx
│   │   ├── websocket/
│   │   │   ├── hitl-modal.tsx
│   │   │   ├── event-log.tsx
│   │   │   └── connection-status.tsx
│   │   ├── layout/
│   │   │   ├── navbar.tsx
│   │   │   ├── sidebar.tsx
│   │   │   └── footer.tsx
│   │   └── common/
│   │       ├── loading-spinner.tsx
│   │       ├── error-boundary.tsx
│   │       └── skeleton-loader.tsx
│   ├── hooks/                      # Custom React hooks
│   │   ├── useAuth.ts
│   │   ├── useWebSocket.ts
│   │   ├── useProfile.ts
│   │   └── useLocalStorage.ts
│   ├── lib/                        # Utilities and configs
│   │   ├── api/                    # API client
│   │   │   ├── client.ts           # Axios instance with interceptors
│   │   │   ├── auth.api.ts         # Auth endpoints
│   │   │   ├── user.api.ts         # User/profile endpoints
│   │   │   └── types.ts            # API response types
│   │   ├── supabase/
│   │   │   ├── client.ts           # Supabase client config
│   │   │   └── server.ts           # Server-side Supabase client
│   │   ├── utils/
│   │   │   ├── formatters.ts       # Date, currency formatters
│   │   │   ├── validators.ts       # Input validators
│   │   │   └── cn.ts               # Tailwind class merger
│   │   └── constants.ts            # App constants
│   ├── store/                      # Zustand stores
│   │   ├── auth.store.ts
│   │   ├── user.store.ts
│   │   └── websocket.store.ts
│   ├── providers/                  # React context providers
│   │   ├── auth-provider.tsx
│   │   ├── query-provider.tsx      # React Query provider
│   │   └── toast-provider.tsx
│   ├── types/                      # TypeScript type definitions
│   │   ├── auth.types.ts
│   │   ├── user.types.ts
│   │   ├── websocket.types.ts
│   │   └── index.ts
│   └── middleware.ts               # Next.js middleware (route protection)
├── .env.local                      # Environment variables
├── .eslintrc.json                  # ESLint config
├── .prettierrc                     # Prettier config
├── next.config.ts                  # Next.js config
├── package.json
├── tsconfig.json                   # TypeScript config
└── tailwind.config.ts              # Tailwind config
```

---

## 🚀 Implementation Roadmap

### Phase 1: Project Setup (Week 1)

**Tasks:**
1. ✅ Initialize Next.js 15 project with TypeScript
2. ✅ Install dependencies (Supabase, Zustand, React Query, shadcn/ui)
3. ✅ Configure Tailwind CSS
4. ✅ Set up ESLint and Prettier
5. ✅ Create folder structure
6. ✅ Configure environment variables
7. ✅ Set up Supabase client

**Deliverables:**
- Working Next.js dev server
- ESLint + Prettier configured
- Folder structure in place

---

### Phase 2: Authentication (Week 2)

**Tasks:**
1. ✅ Implement Supabase client setup
2. ✅ Create auth Zustand store
3. ✅ Build login page
4. ✅ Build signup page
5. ✅ Implement OAuth (Google, GitHub)
6. ✅ Add password reset flow
7. ✅ Create auth middleware
8. ✅ Add auth provider
9. ✅ Test token refresh flow

**Deliverables:**
- Fully functional login/signup
- OAuth working
- Protected routes enforced

---

### Phase 3: User Profile & Onboarding (Week 3-4)

**Tasks:**
1. ✅ Create user API client
2. ✅ Build profile data types
3. ✅ Implement onboarding flow (6 steps)
   - Personal info form
   - Education form
   - Experience form
   - Projects form
   - Skills selector
   - Resume uploader
4. ✅ Create profile dashboard
5. ✅ Build profile edit page
6. ✅ Integrate with backend API
7. ✅ Add form validation (zod)
8. ✅ Test CRUD operations

**Deliverables:**
- Complete onboarding flow
- Profile management working
- Resume upload functional

---

### Phase 4: WebSocket Integration (Week 5)

**Tasks:**
1. ✅ Build useWebSocket hook
2. ✅ Create WebSocket store
3. ✅ Implement auto-reconnect logic
4. ✅ Build HITL modal component
5. ✅ Create event log component
6. ✅ Add connection status indicator
7. ✅ Test WebSocket messages
8. ✅ Test HITL flow

**Deliverables:**
- WebSocket client working
- HITL modal functional
- Event streaming tested

---

### Phase 5: UI/UX Polish (Week 6)

**Tasks:**
1. ✅ Set up shadcn/ui components
2. ✅ Build responsive layouts
3. ✅ Add loading states
4. ✅ Create error boundaries
5. ✅ Implement toast notifications
6. ✅ Add animations (framer-motion)
7. ✅ Mobile responsiveness
8. ✅ Accessibility audit

**Deliverables:**
- Responsive design
- Smooth animations
- WCAG 2.1 AA compliant

---

### Phase 6: Testing & Deployment (Week 7)

**Tasks:**
1. ✅ Write unit tests (Vitest)
2. ✅ Write integration tests
3. ✅ E2E tests (Playwright)
4. ✅ Performance optimization
5. ✅ Lighthouse audit
6. ✅ Deploy to Vercel
7. ✅ Configure production env vars
8. ✅ Monitor with Vercel Analytics

**Deliverables:**
- 80%+ test coverage
- Lighthouse score > 90
- Production deployment

---

## 🔒 Security Best Practices

### 1. **Token Storage**

❌ **Never store JWT in localStorage**
- Vulnerable to XSS attacks
- Any malicious script can steal tokens

✅ **Use Zustand (in-memory) for access tokens**
- Cleared on page refresh (by design)
- Refresh token in HttpOnly cookie (Supabase managed)

### 2. **HTTPS Only**

```typescript
// Force HTTPS in production
if (process.env.NODE_ENV === 'production' && !window.location.protocol.startsWith('https')) {
  window.location.protocol = 'https:';
}
```

### 3. **Content Security Policy**

```typescript
// next.config.ts
const ContentSecurityPolicy = `
  default-src 'self';
  script-src 'self' 'unsafe-eval' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: blob:;
  connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL} ${process.env.NEXT_PUBLIC_WS_URL};
`;

const securityHeaders = [
  {
    key: 'Content-Security-Policy',
    value: ContentSecurityPolicy.replace(/\s{2,}/g, ' ').trim()
  },
  {
    key: 'X-Content-Type-Options',
    value: 'nosniff'
  },
  {
    key: 'X-Frame-Options',
    value: 'DENY'
  }
];
```

### 4. **Input Validation**

```typescript
// Use zod for runtime validation
import { z } from 'zod';

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters')
});

// Validate before sending to API
try {
  const data = loginSchema.parse({ email, password });
  // Proceed with login
} catch (error) {
  // Show validation errors
}
```

### 5. **Rate Limiting**

```typescript
// Implement client-side rate limiting
const rateLimiter = new Map<string, number[]>();

function checkRateLimit(key: string, maxRequests: number, windowMs: number): boolean {
  const now = Date.now();
  const timestamps = rateLimiter.get(key) || [];
  
  // Remove old timestamps
  const validTimestamps = timestamps.filter(t => now - t < windowMs);
  
  if (validTimestamps.length >= maxRequests) {
    return false; // Rate limit exceeded
  }
  
  validTimestamps.push(now);
  rateLimiter.set(key, validTimestamps);
  return true;
}
```

---

## ⚡ Performance Optimization

### 1. **Code Splitting**

```typescript
// Use dynamic imports for heavy components
import dynamic from 'next/dynamic';

const DashboardChart = dynamic(() => import('@/components/dashboard/chart'), {
  loading: () => <ChartSkeleton />,
  ssr: false
});
```

### 2. **Image Optimization**

```typescript
// Use Next.js Image component
import Image from 'next/image';

<Image
  src="/profile.jpg"
  alt="Profile"
  width={200}
  height={200}
  priority={false}
  placeholder="blur"
/>
```

### 3. **API Caching (React Query)**

```typescript
// lib/api/query-client.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
      retry: 2,
      refetchOnWindowFocus: false
    }
  }
});
```

### 4. **Bundle Size Optimization**

```json
// package.json - Use only what you need
{
  "dependencies": {
    "@supabase/supabase-js": "^2.39.0",  // Use latest
    "zustand": "^4.5.0",                  // 1.2KB gzipped
    "@tanstack/react-query": "^5.17.0",  // Tree-shakeable
    "react-hook-form": "^7.49.0",        // 8KB gzipped
    "zod": "^3.22.0"                      // 13KB gzipped
  }
}
```

---

## 🧪 Testing Strategy

### 1. **Unit Tests (Vitest)**

```typescript
// hooks/useAuth.test.ts
import { renderHook, act } from '@testing-library/react';
import { useAuthStore } from '@/store/auth.store';

describe('useAuthStore', () => {
  it('should initialize with no user', () => {
    const { result } = renderHook(() => useAuthStore());
    expect(result.current.user).toBeNull();
  });
  
  it('should set user after login', async () => {
    const { result } = renderHook(() => useAuthStore());
    
    await act(async () => {
      await result.current.login('test@example.com', 'password123');
    });
    
    expect(result.current.user).not.toBeNull();
    expect(result.current.user?.email).toBe('test@example.com');
  });
});
```

### 2. **Integration Tests**

```typescript
// app/login/page.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LoginPage from './page';

describe('LoginPage', () => {
  it('should show validation error for invalid email', async () => {
    render(<LoginPage />);
    
    const emailInput = screen.getByLabelText('Email');
    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
    fireEvent.blur(emailInput);
    
    await waitFor(() => {
      expect(screen.getByText('Invalid email address')).toBeInTheDocument();
    });
  });
  
  it('should call login API on submit', async () => {
    render(<LoginPage />);
    
    const emailInput = screen.getByLabelText('Email');
    const passwordInput = screen.getByLabelText('Password');
    const submitButton = screen.getByText('Sign in');
    
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(mockLoginApi).toHaveBeenCalledWith('test@example.com', 'password123');
    });
  });
});
```

### 3. **E2E Tests (Playwright)**

```typescript
// tests/e2e/auth.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test('should login successfully', async ({ page }) => {
    await page.goto('/login');
    
    await page.fill('[name="email"]', 'test@example.com');
    await page.fill('[name="password"]', 'password123');
    await page.click('button[type="submit"]');
    
    await expect(page).toHaveURL('/dashboard');
    await expect(page.locator('text=Welcome back')).toBeVisible();
  });
  
  test('should redirect to onboarding if no profile', async ({ page }) => {
    await page.goto('/login');
    
    await page.fill('[name="email"]', 'newuser@example.com');
    await page.fill('[name="password"]', 'password123');
    await page.click('button[type="submit"]');
    
    await expect(page).toHaveURL('/onboarding');
  });
});
```

---

## 📊 Environment Variables

```bash
# .env.local
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key

# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# OAuth Providers
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-client-id
NEXT_PUBLIC_GITHUB_CLIENT_ID=your-github-client-id

# App Config
NEXT_PUBLIC_APP_NAME=JobStream
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

---

## 🎯 Success Criteria for Level 1

### Functional Requirements

- ✅ User can sign up with email/password
- ✅ User can log in with email/password
- ✅ User can log in with Google OAuth
- ✅ User can log in with GitHub OAuth
- ✅ User can reset password
- ✅ User is redirected to onboarding after signup
- ✅ User completes 6-step onboarding
- ✅ User can view/edit profile
- ✅ User can upload resume
- ✅ WebSocket connects with JWT token
- ✅ WebSocket auto-reconnects on disconnect
- ✅ HITL modal appears for user input requests
- ✅ Protected routes enforce authentication

### Non-Functional Requirements

- ✅ Lighthouse score > 90 (Performance, Accessibility, Best Practices, SEO)
- ✅ 100% TypeScript coverage (no `any` types)
- ✅ 80%+ test coverage
- ✅ < 3s initial page load
- ✅ < 100ms WebSocket latency
- ✅ Mobile responsive (iPhone, iPad, Android)
- ✅ WCAG 2.1 AA compliant
- ✅ Zero XSS/CSRF vulnerabilities

---

## 📚 Next Steps (Level 2 Preview)

Once Level 1 is complete, Level 2 will add:

1. **Job Search Interface**
   - Search form with filters
   - Job listing cards
   - Job details modal

2. **Pipeline Dashboard**
   - Real-time pipeline status
   - Live event log
   - Browser streaming visualization
   - Pipeline controls (start, stop, pause)

3. **Job Analysis Results**
   - Match score visualization
   - Skills gap analysis
   - Company insights

**Estimated Timeline:** 2-3 weeks after Level 1

---

## 🎓 Conclusion

This Level 1 architecture provides a **production-grade foundation** for the JobStream frontend, with:

✅ **Secure Authentication** (Supabase + JWT)  
✅ **Real-Time Communication** (WebSocket with auto-reconnect)  
✅ **Type-Safe API Client** (Axios + TypeScript)  
✅ **Scalable State Management** (Zustand + React Query)  
✅ **Modern UI/UX** (shadcn/ui + Tailwind CSS)  
✅ **Best Practices** (Security, Performance, Testing)

**Ready for implementation!** 🚀

---

**Last Updated:** February 2, 2026  
**Version:** 1.0  
**Status:** 📋 Planning Complete → Ready for Development
