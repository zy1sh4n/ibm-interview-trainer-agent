# 🎯 IBM Interview Trainer Agent

> **Problem Statement No. 22** — An AI-powered Interview Trainer Agent built on **IBM Granite (WatsonX AI)** with **RAG (Retrieval-Augmented Generation)**, a **multi-agent architecture**, a **Streamlit UI**, a **FastAPI REST API**, and a comprehensive **9-layer guardrail system**.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![IBM WatsonX](https://img.shields.io/badge/IBM-WatsonX%20AI-0f62fe?logo=ibm)](https://www.ibm.com/watsonx)
[![IBM Granite](https://img.shields.io/badge/IBM-Granite%2013B-0043ce?logo=ibm)](https://www.ibm.com/granite)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-red?logo=streamlit)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📌 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [9-Layer Guardrail System](#9-layer-guardrail-system)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Running the App](#running-the-app)
- [API Reference](#api-reference)
- [Streamlit UI Guide](#streamlit-ui-guide)
- [Configuration](#configuration)
- [Technology Stack](#technology-stack)
- [IBM Cloud Services](#ibm-cloud-services)
- [Testing](#testing)
- [How RAG Works](#how-rag-works)
- [Example Usage](#example-usage)

---

## Overview

The **IBM Interview Trainer Agent** prepares job candidates for interviews by generating tailored question sets, analyzing resumes, evaluating answers, and building personalized preparation plans — all powered by **IBM Granite LLM** via **WatsonX AI**.

It uses **Retrieval-Augmented Generation (RAG)** to ground every response in a curated knowledge base of role-specific questions, industry expectations, behavioral scenarios, and HR guidelines — ensuring accurate, relevant, and helpful content.

Every interaction is protected by a **9-layer guardrail architecture** covering input safety, output quality, data privacy, security, operational limits, human oversight, multi-agent coordination, and ethical compliance.

---

## Features

| Feature | Description |
|---------|-------------|
| 🤖 **IBM Granite LLM** | Uses `ibm/granite-13b-chat-v2` via WatsonX AI SDK |
| 📚 **RAG Engine** | Pure-Python in-memory TF-IDF retrieval, no external vector DB needed |
| 🛡️ **9-Layer Guardrails** | Full guardrail stack from input validation to ethical compliance |
| 📋 **Question Generator** | Technical, Behavioral (STAR), and HR questions with model answers |
| 📄 **Resume Analyzer** | Gap analysis, strengths, improvement tips, interview focus areas |
| ✏️ **Answer Evaluator** | Scored feedback (1–10), strengths, improvement suggestions, model answer |
| 📅 **Prep Plan Builder** | Day-by-day study schedule with mock interview slots |
| 🏆 **Full Pipeline** | One-click complete preparation package (all 5 features at once) |
| 🌐 **Streamlit UI** | Beautiful, interactive web interface |
| ⚡ **FastAPI REST API** | 17 REST endpoints with full OpenAPI docs |
| 🔒 **Data Privacy** | GDPR-compliant consent management, PII redaction, anonymization |
| 🧪 **34-Test Validation** | Full validation suite, all tests passing |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Streamlit UI (Port 8501)                     │
│                         streamlit_app.py                            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ direct Python calls
┌───────────────────────────────▼─────────────────────────────────────┐
│                    FastAPI REST API (Port 8000)                     │
│                    main.py — 17 endpoints                           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
              ┌─────────────────▼──────────────────┐
              │        Interview Trainer Agent      │
              │    agents/interview_trainer_agent.py │
              └──────┬──────────────────────────────┘
                     │
     ┌───────────────┼───────────────────────────────┐
     │               │                               │
     ▼               ▼                               ▼
 RAG Engine    IBM Granite Client           9-Layer Guardrails
 rag_engine.py ibm_granite_client.py        guardrails/*.py
     │               │
     ▼               ▼
In-Memory        WatsonX AI
Knowledge      ibm/granite-13b-chat-v2
Base (11 docs)
```

### Multi-Agent Orchestration

```
Orchestrator Agent
    ├── Question Generator Agent   → technical, behavioral, HR questions
    ├── Resume Analyzer Agent      → gap analysis, skill matching
    ├── Answer Evaluator Agent     → scoring, feedback, model answers
    ├── Prep Planner Agent         → day-by-day study schedules
    └── Full Pipeline Agent        → coordinates all 4 agents above
```

---

## 9-Layer Guardrail System

Every user interaction passes through all 9 guardrail layers:

### Layer 1 — Input Guardrails (`input_guardrails.py`)
| Control | Description |
|---------|-------------|
| **Prompt Injection Detection** | Regex-based detection of 12 injection patterns (e.g. "ignore all previous instructions", "DAN mode") |
| **Malicious Content Detection** | Blocks SQL injection, XSS, `os.system()`, `subprocess`, JavaScript injection |
| **PII Detection & Redaction** | Auto-detects and redacts emails, phone numbers, SSNs before sending to LLM |
| **Inappropriate Content Filter** | Blocks harmful keywords and violent content |
| **Length Validation** | Enforces min/max character limits on all inputs |

### Layer 2 — Output Guardrails (`output_guardrails.py`)
| Control | Description |
|---------|-------------|
| **Hallucination Detection** | Heuristic overlap scoring against RAG context documents |
| **Toxicity Filtering** | Detects toxic/harmful language in AI-generated responses |
| **Sensitive Info Redaction** | Strips API keys, passwords, secrets from output |
| **Response Length Enforcement** | Truncates responses exceeding configured max length |
| **Factual Accuracy Heuristic** | Word-overlap scoring against retrieved knowledge documents |

### Layer 3 — Tool Execution Guardrails (`tool_guardrails.py`)
| Control | Description |
|---------|-------------|
| **Tool Access Permissions** | Allowlist-based tool authorization per agent |
| **API Authorization** | Token-based auth check before every external call |
| **Function-Call Validation** | Parameter type and range validation before execution |
| **Rate Limiting** | Per-tool call rate limits (configurable) |
| **Sandboxed Execution** | Execution timeout per tool call |

### Layer 4 — Data Privacy Guardrails (`data_privacy_guardrails.py`)
| Control | Description |
|---------|-------------|
| **Consent Management** | GDPR-compliant consent recording, purpose validation, withdrawal |
| **Data Anonymization** | SHA-256-based field-level anonymization of PII fields |
| **Pseudonymization** | Deterministic pseudonym generation from user IDs |
| **Access Control** | Owner/admin access checks on all data operations |
| **Retention Policy** | Configurable data expiry; expired records blocked |

### Layer 5 — Security Guardrails (`security_guardrails.py`)
| Control | Description |
|---------|-------------|
| **Jailbreak Detection** | 9-pattern regex detection (developer mode, sudo mode, god mode, etc.) |
| **SQL Injection Prevention** | Full SQL injection pattern matching |
| **Brute-Force Lockout** | Auto-lockout after N failed attempts within a time window |
| **HMAC Cross-Agent Signing** | SHA-256 HMAC message signing for secure agent-to-agent communication |
| **Prompt Injection Protection** | Shared with Layer 1; enforced at both input and agent-to-agent boundaries |

### Layer 6 — Operational Guardrails (`operational_guardrails.py`)
| Control | Description |
|---------|-------------|
| **Execution Timeout** | Configurable per-request timeout (default: 120s) |
| **Infinite Loop Detection** | Fingerprint-based repeated-step detection |
| **Token Budget Tracking** | Per-request, per-session, and monthly token limits |
| **Rate Limiting** | Request-per-minute quota enforcement |
| **Retry with Back-off** | Exponential back-off retry (configurable max retries) |

### Layer 7 — Human-in-the-Loop Guardrails (`hitl_guardrails.py`)
| Control | Description |
|---------|-------------|
| **Approval Request Queue** | Critical actions queued for human review |
| **Approve / Reject API** | REST endpoints for human operators to approve or reject |
| **Auto-Escalation** | Requests pending beyond timeout auto-escalate |
| **Pending Audit Trail** | Full history of all HITL decisions |

### Layer 8 — Multi-Agent Guardrails (`multi_agent_guardrails.py`)
| Control | Description |
|---------|-------------|
| **Agent Registration** | Idempotent registration with capability declaration |
| **Access Control** | Per-agent tool and data access permissions |
| **Task Assignment Validation** | Role-based task routing checks |
| **Cross-Agent Verification** | Output verification before forwarding between agents |
| **Infinite Loop Prevention** | Max-handoff counter; deadlock detection |

### Layer 9 — Ethical & Compliance Guardrails (`ethical_guardrails.py`)
| Control | Description |
|---------|-------------|
| **Gender Bias Detection** | Flags gender-biased language in generated content |
| **Age Bias Detection** | Flags age-discriminatory statements |
| **EEO Illegal Question Detection** | Blocks questions about religion, marital status, disability, etc. |
| **Fairness Scoring** | Quantitative fairness metric (0.0–1.0) per response |
| **AI Disclaimer Injection** | Mandatory AI-disclosure footer on preparation plans |
| **Audit Trail** | Full JSON audit log of every ethical check (last 1000 records) |

---

## Project Structure

```
IBM PROJECT/
│
├── .env                             # Environment variables (IBM credentials)
├── requirements.txt                 # Python dependencies
├── main.py                          # FastAPI application (17 endpoints)
├── run.py                           # Uvicorn server entry point
├── streamlit_app.py                 # Streamlit web UI (6 tabs)
├── validate.py                      # 34-test validation suite
├── README.md                        # This file
│
├── config/
│   ├── __init__.py
│   └── settings.py                  # Pydantic v2 settings (all env vars)
│
├── core/
│   ├── __init__.py
│   ├── ibm_granite_client.py        # IBM WatsonX AI / Granite SDK wrapper
│   └── rag_engine.py                # Pure-Python RAG (TF-IDF, 11 knowledge docs)
│
├── agents/
│   ├── __init__.py
│   ├── interview_trainer_agent.py   # Core agent: 5 public functions
│   └── orchestrator.py              # Multi-agent orchestrator
│
├── guardrails/
│   ├── __init__.py
│   ├── input_guardrails.py          # Layer 1: Input validation
│   ├── output_guardrails.py         # Layer 2: Output validation
│   ├── tool_guardrails.py           # Layer 3: Tool execution control
│   ├── data_privacy_guardrails.py   # Layer 4: GDPR & privacy
│   ├── security_guardrails.py       # Layer 5: Security & anti-jailbreak
│   ├── operational_guardrails.py    # Layer 6: Timeouts & token budgets
│   ├── hitl_guardrails.py           # Layer 7: Human-in-the-Loop
│   ├── multi_agent_guardrails.py    # Layer 8: Multi-agent coordination
│   └── ethical_guardrails.py        # Layer 9: Bias, EEO, fairness
│
├── utils/
│   ├── __init__.py
│   └── logger.py                    # Structured logging utility
│
├── tests/
│   ├── __init__.py
│   └── test_guardrails.py           # pytest test suite
│
├── data/
│   └── vector_store/                # RAG document storage (in-memory)
│
└── logs/
    ├── interview_trainer.log         # Application logs
    └── audit.log                     # Ethical audit trail (JSON)
```

---

## Setup & Installation

### Prerequisites
- Python 3.10 or higher
- An **IBM WatsonX AI** account (IBM Cloud Lite is sufficient)
- Your **IBM WatsonX API Key** and **Project ID**

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/ibm-interview-trainer-agent.git
cd ibm-interview-trainer-agent
```

### 2. Create a Virtual Environment
```bash
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root with your IBM credentials:

```env
# ── MANDATORY: IBM WatsonX AI ──────────────────────────────
IBM_WATSONX_API_KEY=your_ibm_watsonx_api_key_here
IBM_WATSONX_URL=https://us-south.ml.cloud.ibm.com
IBM_WATSONX_PROJECT_ID=your_project_id_here

# ── Model (defaults work fine) ─────────────────────────────
IBM_GRANITE_MODEL_ID=ibm/granite-13b-chat-v2

# ── App Settings ───────────────────────────────────────────
APP_SECRET_KEY=change_this_to_a_random_32char_string
APP_ENV=development
```

> **That's all you need.** The three IBM lines above are the only mandatory settings.
> Everything else in the `.env` uses sensible defaults.

### How to get your IBM WatsonX credentials:
1. Go to [cloud.ibm.com](https://cloud.ibm.com) → sign up for a free Lite account
2. Navigate to **WatsonX** → **Projects** → create or open a project
3. Copy your **Project ID** from the project settings
4. Go to **Manage** → **Access (IAM)** → **API keys** → create a new API key

---

## Running the App

### Option A — Streamlit UI (Recommended)
```bash
streamlit run streamlit_app.py
```
Opens at: **http://localhost:8501**

### Option B — FastAPI REST API
```bash
python run.py
# OR
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
- Swagger UI: **http://localhost:8000/docs**
- ReDoc: **http://localhost:8000/redoc**
- Health: **http://localhost:8000/health**

### Option C — Run Validation Suite
```bash
python validate.py
```
Expected output: `ALL TESTS PASSED  OK` (34 tests)

---

## API Reference

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/health` | Health check + model status |
| `GET`  | `/api/v1/usage` | Token usage & budget stats |
| `GET`  | `/api/v1/agent/status` | Multi-agent system status |

### Consent (GDPR)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/consent` | Record user consent |
| `GET`  | `/api/v1/consent/{user_id}` | Check consent status |

### Interview Preparation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/questions` | Generate interview questions |
| `POST` | `/api/v1/resume/analyze` | Analyze resume + gap analysis |
| `POST` | `/api/v1/answer/evaluate` | Score and evaluate an answer |
| `POST` | `/api/v1/plan` | Create preparation plan |
| `POST` | `/api/v1/prepare` | Full preparation pipeline |

### Human-in-the-Loop

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/hitl/approve` | Approve a pending HITL request |
| `POST` | `/api/v1/hitl/reject` | Reject a pending HITL request |
| `GET`  | `/api/v1/hitl/pending` | List all pending approvals |

### Request Body Example — Generate Questions
```json
POST /api/v1/questions
{
  "profile": {
    "name": "Alice Johnson",
    "job_role": "Senior Software Engineer",
    "experience_level": "senior"
  },
  "question_type": "technical",
  "num_questions": 10
}
```

### Response Example
```json
{
  "success": true,
  "session_id": "abc123",
  "candidate": "Alice Johnson",
  "job_role": "Senior Software Engineer",
  "level": "senior",
  "question_type": "technical",
  "content": "Q: Explain the CAP theorem...\nA: ...\nTips: ...",
  "warnings": [],
  "guardrail_flags": [],
  "tokens_used": 312,
  "powered_by": "IBM Granite"
}
```

---

## Streamlit UI Guide

The Streamlit app has **6 tabs**:

| Tab | Feature | Description |
|-----|---------|-------------|
| 📋 **Questions** | Question Generator | Choose type (technical/behavioral/HR/all), set count, generate with model answers |
| 📄 **Resume** | Resume Analyzer | Paste resume text → get strengths, gaps, focus areas |
| ✏️ **Evaluator** | Answer Evaluator | Enter a question + your answer → get scored feedback (1–10) |
| 📅 **Plan** | Prep Plan | Slider for 7–30 days → get day-by-day schedule |
| 🏆 **Full Prep** | Complete Pipeline | Runs all 4 steps at once, download full report |
| 🛡️ **Guardrails** | Dashboard | Live status of all 9 guardrail layers + runtime stats |

**Sidebar** contains:
- Candidate profile (name, job role, experience level)
- GDPR consent checkbox (required before any feature)
- Session info (ID, token count, request count)
- Model status (live vs mock)
- New Session button

---

## Configuration

All settings are controlled via `.env`. Key settings:

```env
# ── Guardrails ─────────────────────────────────────────────
GUARDRAIL_PII_DETECTION_ENABLED=True
GUARDRAIL_PROMPT_INJECTION_ENABLED=True
GUARDRAIL_JAILBREAK_DETECTION_ENABLED=True
GUARDRAIL_HALLUCINATION_CHECK_ENABLED=True
GUARDRAIL_TOXICITY_FILTER_ENABLED=True
BIAS_DETECTION_ENABLED=True
AUDIT_TRAIL_ENABLED=True

# ── Token Limits ───────────────────────────────────────────
GUARDRAIL_MAX_TOKENS_PER_REQUEST=2048
GUARDRAIL_MAX_TOKENS_PER_SESSION=20000
GUARDRAIL_MONTHLY_TOKEN_BUDGET=1000000

# ── Rate Limiting ──────────────────────────────────────────
GUARDRAIL_RATE_LIMIT_REQUESTS_PER_MINUTE=30
GUARDRAIL_EXECUTION_TIMEOUT_SECONDS=120
GUARDRAIL_MAX_RETRIES=3

# ── Data Privacy ───────────────────────────────────────────
CONSENT_REQUIRED=True
ANONYMIZATION_ENABLED=True
DATA_RETENTION_DAYS=90

# ── Human-in-the-Loop ──────────────────────────────────────
HITL_APPROVAL_REQUIRED=True
HITL_APPROVAL_TIMEOUT_SECONDS=300
```

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **LLM** | IBM Granite 13B Chat v2 | via WatsonX AI |
| **AI Platform** | IBM WatsonX AI | `ibm-watsonx-ai` SDK |
| **RAG** | Pure-Python TF-IDF (in-memory) | Custom implementation |
| **Web UI** | Streamlit | ≥ 1.40 |
| **REST API** | FastAPI | ≥ 0.115 |
| **Settings** | Pydantic v2 + pydantic-settings | ≥ 2.0 |
| **Server** | Uvicorn | ≥ 0.29 |
| **Testing** | pytest + custom validate.py | — |
| **Runtime** | Python | 3.10+ |

---

## IBM Cloud Services

| Service | Role in This Project | Required? |
|---------|---------------------|-----------|
| **IBM WatsonX AI** | Hosts IBM Granite LLM | ✅ **Mandatory** |
| **IBM Granite 13B Chat v2** | Question generation, evaluation, planning | ✅ **Mandatory** |
| **IBM Cloud Lite Account** | Free tier — sufficient for this project | ✅ **Mandatory** |
| IBM Cloud Object Storage | Document storage for RAG | ⚪ Optional |
| IBM Cloudant | Session & audit log persistence | ⚪ Optional |
| IBM Watson Discovery | Advanced retrieval | ⚪ Optional |
| IBM Watson NLU | NLP analysis | ⚪ Optional |

> **Only one API key is needed** — your IBM WatsonX API key. The RAG knowledge base is built in-memory; no additional IBM services are required to run the full project.

---

## Testing

### Run the validation suite (34 tests):
```bash
python validate.py
```

### Run pytest:
```bash
pytest tests/ -v
```

### What is tested:
| Test Group | Tests |
|-----------|-------|
| Input Guardrails | Injection detection, PII detection, length validation, clean pass |
| Output Guardrails | Toxicity detection, hallucination risk, sensitive info redaction |
| Tool Execution Guardrails | Allowed tool, blocked tool, rate limit |
| Data Privacy Guardrails | Consent record, consent check, anonymization |
| Security Guardrails | Jailbreak detection, SQL injection, clean pass |
| Operational Guardrails | Token budget, loop detection |
| Human-in-the-Loop | Approval request, approve, reject, pending list |
| Multi-Agent Guardrails | Agent registration, access check, cross-agent messaging |
| Ethical & Compliance | Neutral content, EEO violation, AI disclaimer |
| IBM Granite Client | Mock response, token estimate |
| RAG Engine | Knowledge base size, retrieval, prompt building |

---

## How RAG Works

```
User Query
    │
    ▼
RAG Engine (rag_engine.py)
    │
    ├── 1. Retrieve: TF-IDF keyword scoring across 11 knowledge documents
    │         Documents cover: technical interviews, behavioral STAR method,
    │         HR questions, resume tips, salary negotiation, system design,
    │         leadership, coding interviews, data science, product management,
    │         and DevOps interviews
    │
    ├── 2. Augment: Top-K docs (default: 3) injected into prompt as context
    │
    └── 3. Generate: Augmented prompt sent to IBM Granite → response returned
```

The knowledge base contains **11 curated documents** covering:
- Software engineering technical interviews
- Behavioral STAR-method questions
- HR and soft skills interviews
- Resume writing best practices
- Salary negotiation strategies
- System design interviews
- Leadership and management questions
- Coding challenge preparation
- Data science and ML interviews
- Product management interviews
- DevOps and cloud infrastructure

---

## Example Usage

### Via Streamlit UI

1. Open `http://localhost:8501`
2. Fill in your name, job role, and experience level in the sidebar
3. Tick the **consent checkbox**
4. Click any tab and hit **Generate** / **Analyze** / **Evaluate**

### Via cURL

```bash
# 1. Record consent
curl -X POST http://localhost:8000/api/v1/consent \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user_001","consented":true,"purposes":["interview_prep"]}'

# 2. Generate 10 technical questions for a Senior Python Developer
curl -X POST http://localhost:8000/api/v1/questions \
  -H "Content-Type: application/json" \
  -H "x-user-id: user_001" \
  -d '{
    "profile": {"name":"Alice","job_role":"Python Developer","experience_level":"senior"},
    "question_type": "technical",
    "num_questions": 10
  }'

# 3. Evaluate your answer
curl -X POST http://localhost:8000/api/v1/answer/evaluate \
  -H "Content-Type: application/json" \
  -H "x-user-id: user_001" \
  -d '{
    "profile": {"job_role":"Python Developer","experience_level":"senior"},
    "question": "What is the GIL in Python?",
    "candidate_answer": "The GIL is a mutex that protects access to Python objects..."
  }'

# 4. Full preparation pipeline
curl -X POST http://localhost:8000/api/v1/prepare \
  -H "Content-Type: application/json" \
  -H "x-user-id: user_001" \
  -d '{
    "profile": {"name":"Alice","job_role":"Python Developer","experience_level":"senior"},
    "days_until_interview": 14
  }'
```

---

## Security Notes

- **Never commit your `.env` file** — it is listed in `.gitignore`
- The `.env` file contains your IBM API key; keep it local only
- In production, use **IBM Secrets Manager** or environment variables injected by your CI/CD pipeline
- The `APP_SECRET_KEY` must be at least 32 characters and randomly generated

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Author

**Mohammad Zeeshan**  
📧 mohammad.zeeshan7674@gmail.com  
🏢 IBM Cloud Lite — Problem Statement No. 22

---

*Built with IBM Granite · WatsonX AI · FastAPI · Streamlit · 9-Layer Guardrail Architecture*
