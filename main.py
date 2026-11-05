"""
IBM Interview Trainer Agent — FastAPI Application
Lean, deployable REST API. Zero heavy deps.
Runs on Python 3.14 with: uvicorn main:app --reload
"""
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from config.settings import get_settings
import guardrails.data_privacy_guardrails as priv
import guardrails.hitl_guardrails as hitl
import guardrails.operational_guardrails as ops
import guardrails.security_guardrails as sec
import guardrails.multi_agent_guardrails as ma
from agents.interview_trainer_agent import (
    generate_questions, analyze_resume, evaluate_answer, create_plan, full_prepare
)

cfg = get_settings()

# -----------------------------------------------------------------------
# Register specialist agents at startup
# -----------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    ma.register("orch", "orchestrator")
    ma.register("qgen", "question_generator")
    ma.register("eval", "answer_evaluator")
    ma.register("resume", "resume_analyzer")
    ma.register("planner", "prep_planner")
    ma.register("hr", "hr_advisor")
    yield


app = FastAPI(
    title=cfg.app_name,
    version=cfg.app_version,
    description=(
        "IBM Interview Trainer Agent · IBM Granite (WatsonX AI) · RAG · "
        "9-layer guardrails · Multi-agent architecture"
    ),
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# -----------------------------------------------------------------------
# Security middleware — runs on every request
# -----------------------------------------------------------------------
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    body = b""
    try:
        body = await request.body()
    except Exception:
        pass
    snippet = body[:400].decode("utf-8", errors="ignore")
    ip = request.client.host if request.client else "unknown"
    safe, threat = sec.check(snippet, ip=ip, user_agent=request.headers.get("user-agent", ""))
    if not safe:
        return JSONResponse(status_code=403,
                            content={"error": "Blocked by security guardrails", "threat": threat})
    return await call_next(request)


# -----------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------
LEVELS = {"entry", "mid", "senior", "executive"}
QTYPES = {"technical", "behavioral", "hr", "all"}


class ConsentBody(BaseModel):
    user_id: str
    consented: bool
    purposes: List[str] = ["interview_preparation"]


class QuestionBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    job_role: str = Field(..., min_length=2, max_length=100)
    level: str = Field(default="mid")
    question_type: str = Field(default="all")
    num_questions: int = Field(default=10, ge=1, le=20)

    @field_validator("level")
    @classmethod
    def level_ok(cls, v):
        if v not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        return v

    @field_validator("question_type")
    @classmethod
    def qtype_ok(cls, v):
        if v not in QTYPES:
            raise ValueError(f"question_type must be one of {QTYPES}")
        return v


class ResumeBody(BaseModel):
    name: str = Field(..., min_length=1)
    job_role: str = Field(..., min_length=2)
    level: str = Field(default="mid")
    resume_text: str = Field(..., min_length=50, max_length=8000)


class EvalBody(BaseModel):
    job_role: str
    level: str = "mid"
    question: str = Field(..., min_length=10)
    candidate_answer: str = Field(..., min_length=10, max_length=3000)


class PlanBody(BaseModel):
    name: str
    job_role: str
    level: str = "mid"
    days: int = Field(default=14, ge=1, le=90)


class PrepBody(BaseModel):
    name: str
    job_role: str
    level: str = "mid"
    resume_text: Optional[str] = None
    days: int = Field(default=14, ge=1, le=90)


class HITLApprove(BaseModel):
    request_id: str
    reviewer_id: str
    notes: str = ""


class HITLReject(BaseModel):
    request_id: str
    reviewer_id: str
    reason: str


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
async def get_uid(x_user_id: Optional[str] = Header(default=None)) -> str:
    return x_user_id or f"anon_{uuid.uuid4().hex[:8]}"

async def get_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")

def require_consent(uid: str):
    ok, reason = priv.check_consent(uid, "interview_preparation")
    if not ok:
        raise HTTPException(403, f"Consent required: {reason}. POST /api/v1/consent first.")


# -----------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "app": cfg.app_name, "version": cfg.app_version,
            "env": cfg.app_env, "granite_model": cfg.ibm_granite_model_id}


@app.post("/api/v1/consent", tags=["Privacy"])
def record_consent(body: ConsentBody, request: Request):
    """Record GDPR consent. Must be called before using prep endpoints."""
    ip = request.client.host if request.client else "unknown"
    rec = priv.record_consent(body.user_id, body.consented, body.purposes, ip)
    return {"message": "Consent recorded.", "consent": rec}


@app.get("/api/v1/consent/{user_id}", tags=["Privacy"])
def check_consent(user_id: str):
    ok, reason = priv.check_consent(user_id, "interview_preparation")
    return {"user_id": user_id, "has_consent": ok, "reason": reason}


@app.post("/api/v1/questions", tags=["Interview Prep"])
async def questions(body: QuestionBody, request: Request,
                    uid: str = Header(default=None, alias="x-user-id")):
    """Generate tailored interview questions using IBM Granite + RAG."""
    user_id = uid or f"anon_{uuid.uuid4().hex[:8]}"
    require_consent(user_id)
    ip = await get_ip(request)
    result = generate_questions(body.name, body.job_role, body.level,
                                body.question_type, body.num_questions,
                                user_id, ip=ip)
    if not result["success"]:
        raise HTTPException(400, result.get("error", "Generation failed"))
    return result


@app.post("/api/v1/resume/analyze", tags=["Interview Prep"])
async def resume_analyze(body: ResumeBody,
                         uid: str = Header(default=None, alias="x-user-id")):
    """Analyze resume: strengths, gaps, interview focus areas."""
    user_id = uid or f"anon_{uuid.uuid4().hex[:8]}"
    require_consent(user_id)
    result = analyze_resume(body.name, body.job_role, body.level,
                            body.resume_text, user_id)
    if not result["success"]:
        raise HTTPException(400, result.get("error", "Analysis failed"))
    return result


@app.post("/api/v1/answer/evaluate", tags=["Interview Prep"])
async def answer_eval(body: EvalBody,
                      uid: str = Header(default=None, alias="x-user-id")):
    """Evaluate a candidate answer: score, strengths, improvement tips."""
    user_id = uid or f"anon_{uuid.uuid4().hex[:8]}"
    require_consent(user_id)
    result = evaluate_answer(body.job_role, body.level, body.question,
                             body.candidate_answer, user_id)
    if not result["success"]:
        raise HTTPException(400, result.get("error", "Evaluation failed"))
    return result


@app.post("/api/v1/plan", tags=["Interview Prep"])
async def prep_plan(body: PlanBody,
                    uid: str = Header(default=None, alias="x-user-id")):
    """Generate a day-by-day interview preparation plan."""
    user_id = uid or f"anon_{uuid.uuid4().hex[:8]}"
    require_consent(user_id)
    result = create_plan(body.name, body.job_role, body.level, body.days, user_id)
    if not result["success"]:
        raise HTTPException(400, result.get("error", "Plan generation failed"))
    return result


@app.post("/api/v1/prepare", tags=["Interview Prep"])
async def prepare(body: PrepBody, request: Request,
                  uid: str = Header(default=None, alias="x-user-id")):
    """Full preparation pipeline: questions + resume + plan in one call."""
    user_id = uid or f"anon_{uuid.uuid4().hex[:8]}"
    require_consent(user_id)
    ip = await get_ip(request)
    result = full_prepare(body.name, body.job_role, body.level,
                          body.resume_text, body.days, user_id, ip=ip)
    return result


@app.get("/api/v1/usage", tags=["System"])
def usage():
    """Token usage and budget utilization report."""
    return ops.usage()


@app.post("/api/v1/hitl/approve", tags=["Human-in-the-Loop"])
def approve(body: HITLApprove):
    """Human reviewer approves a pending HITL request."""
    ok = hitl.approve(body.request_id, body.reviewer_id, body.notes)
    if not ok:
        raise HTTPException(404, f"Request '{body.request_id}' not found or already processed.")
    return {"message": "Approved.", "request_id": body.request_id}


@app.post("/api/v1/hitl/reject", tags=["Human-in-the-Loop"])
def reject(body: HITLReject):
    """Human reviewer rejects a pending HITL request."""
    ok = hitl.reject(body.request_id, body.reviewer_id, body.reason)
    if not ok:
        raise HTTPException(404, f"Request '{body.request_id}' not found.")
    return {"message": "Rejected.", "request_id": body.request_id}


@app.get("/api/v1/hitl/pending", tags=["Human-in-the-Loop"])
def pending():
    """List all pending HITL approval requests."""
    p = hitl.pending()
    return {"count": len(p), "requests": p}


@app.get("/api/v1/agents", tags=["System"])
def agent_status():
    """Multi-agent registration and communication log."""
    return {"message_log": ma.message_log()}


@app.exception_handler(Exception)
async def global_exc(request: Request, exc: Exception):
    return JSONResponse(500, {"error": "Internal server error.", "id": str(uuid.uuid4())})
