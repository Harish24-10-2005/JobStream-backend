# JobAI - Autonomous Job Application Agent

JobAI is a dual-agent system designed to automate the painful process of applying for jobs. It combines a powerful backend orchestrator with a modern Next.js frontend to scout, analyze, research, tailor resumes, and auto-apply to jobs with Human-in-the-Loop (HITL) control.

## 🚀 Features

- **🕵️ Job Scout**: Scrapes job boards (LinkedIn, etc.) for relevant positions based on natural language queries.
- **📊 Job Analyst**: Analyzes JD vs. Resume match score, identifying missing skills and key keywords.
- **🏢 Company Researcher**: Performs deep research on company culture, recent news, and interview red flags using SerpAPI.
- **📝 Resume Tailor**: Dynamically rewrites your resume (PDF) to highlight relevant experience for each specific job.
- **✍️ Cover Letter Agent**: Drafts personalized cover letters based on the job description and your background.
- **🤖 Live Applier**: Autonomous browser agent that navigates job portals, fills forms, and uploads documents.
- **🕹️ Human-in-the-Loop**: WebSocket-based real-time interaction. The agent asks for permission before submitting or when it encounters ambiguity.
- **🖥️ Live Streaming**: Watch the agent's browser view in real-time on your dashboard.

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, LangChain, LangGraph, Browser-use (Playwright), WebSockets.
- **Frontend**: Next.js 14, TailwindCSS, Shadcn/UI, Framer Motion, TypeScript.
- **AI Models**: Supports OpenRouter (Qwen/DeepSeek/Llama), Google Gemini, Groq.

## 📋 Prerequisites

- Python 3.10+
- Node.js 18+
- Google Chrome (for browser automation)

## ⚡ Setup Instructions

### 1. clone the repository
```bash
git clone https://github.com/your-repo/jobai.git
cd jobai
```

### 2. Backend Setup
Navigate to the `backend` directory.

```bash
cd backend
```

```bash
# Create virtual environment
python -m venv venv
# Activate it (Windows)
.\venv\Scripts\activate
# Activate it (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install
```

Create a `.env` file in the `backend/` directory with the following credentials:
```env
OPENAI_API_KEY=sk-...         # Optional, if using OpenAI
OPENROUTER_API_KEY=sk-or-...  # Recommended for cost/performance
GROQ_API_KEY=gsk_...          # Fast inference for minor tasks
GEMINI_API_KEY=...            # Google Gemini
SERPAPI_API_KEY=...           # For Company Research
```

### 3. Frontend Setup
Navigate to the frontend directory.

```bash
cd ../frontend
npm install
```

## 🏃‍♂️ Running the Application

### Start the Backend
From the `backend` directory:
```bash
python main.py
```
Server runs on `http://localhost:8000`.

### Start the Frontend
From the `frontend` directory:
```bash
npm run dev
```
App runs on `http://localhost:3000`.

## 🎮 Usage

1. Open `http://localhost:3000`.
2. **Pipeline Mode**:
   - Enter a job search query (e.g., "Senior Python Dev").
   - Toggle optional agents (Company Research, Resume Tailor, Cover Letter).
   - Click "Start Agent".
   - View the progress in the "Action Log" and live status badges.
   - When HITL is requested (e.g., to approve a resume), a modal will appear.

3. **Direct Apply Mode**:
   - Switch tabs to "Direct Apply".
   - Paste a specific job URL (Greenhouse/Lever/Ashby).
   - Click "Apply".
   - Watch the Live Browser view as the agent fills the form.
   - Using the Chat interface to guide the agent if it gets stuck.

## 🐳 Docker (Optional)

Coming soon.