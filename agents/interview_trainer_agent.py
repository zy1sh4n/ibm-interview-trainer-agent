"""
IBM Interview Trainer Agent
Orchestrates RAG + IBM Granite + all 9 guardrails.
"""
import uuid, time, re, logging
from typing import Any, Dict, List, Optional

from config.settings import get_settings
from core.ibm_granite_client import GraniteClient
from core import rag_engine as rag
import guardrails.input_guardrails as ing
import guardrails.output_guardrails as oug
import guardrails.security_guardrails as sec
import guardrails.operational_guardrails as ops
import guardrails.ethical_guardrails as eth
import guardrails.data_privacy_guardrails as priv

cfg = get_settings()
log = logging.getLogger("agent")

# Shared Granite client (one instance for the whole process)
_granite = GraniteClient()


def _session() -> str:
    return str(uuid.uuid4())


# -----------------------------------------------------------------------
# Core pipeline
# -----------------------------------------------------------------------

def _rag_generate(query: str, user_ctx: Dict, session_id: str, max_tokens: int = 800) -> Dict:
    """Retrieve → augment → generate. Returns {text, tokens, mock}."""
    docs = rag.retrieve(query)
    prompt = rag.build_prompt(query, docs, user_ctx)
    result = _granite.generate(prompt, max_tokens=max_tokens)
    ops.record_tokens(result.get("tokens", 0), session_id)
    return {**result, "docs": docs}


def _guardrailed_call(
    query: str,
    user_ctx: Dict,
    session_id: str,
    user_id: str = "anon",
    content_type: str = "answer",
    max_tokens: int = 800,
) -> Dict[str, Any]:
    """Full guardrail-wrapped call: input → RAG+Granite → output → ethical."""

    # 1. Input guardrail
    ir = ing.validate(query, user_id)
    if not ir.is_valid:
        return {"success": False, "error": f"Input blocked: {ir.violations}", "text": ""}

    # 2. Token budget
    ok, msg = ops.budget_ok(max_tokens, session_id)
    if not ok:
        return {"success": False, "error": msg, "text": ""}

    # 3. Generate
    result = _rag_generate(ir.clean, user_ctx, session_id, max_tokens)

    # 4. Output guardrail
    doc_texts = [d["content"] for d in result.get("docs", [])]
    oр = oug.validate(result.get("text", ""), context_docs=doc_texts)

    # 5. Ethical check
    eth_r = eth.check(oр.text, content_type, user_id, session_id)
    final_text = oр.text
    if not eth_r["passed"]:
        log.warning(f"Ethical flag: {eth_r['explanation']}")

    return {
        "success": True,
        "text": final_text,
        "tokens": result.get("tokens", 0),
        "mock": result.get("mock", True),
        "warnings": oр.warnings + eth_r.get("recommendations", []),
        "guardrail_flags": oр.violations,
    }


# -----------------------------------------------------------------------
# Public functions
# -----------------------------------------------------------------------

QUESTION_TEMPLATES = {
    "technical": (
        "Generate {n} technical interview questions for a {level}-level {role}. "
        "For each question provide: (1) the question, (2) a model answer, (3) two improvement tips. "
        "Format each as Q: ... | A: ... | Tips: ..."
    ),
    "behavioral": (
        "Generate {n} behavioral STAR-method interview questions for a {level}-level {role}. "
        "For each provide: (1) the question, (2) a model answer using the STAR method, "
        "(3) two improvement tips."
    ),
    "hr": (
        "Generate {n} HR interview questions for a {level}-level {role}. "
        "Include questions about motivation, culture fit, salary expectations, and career goals. "
        "For each provide: (1) the question, (2) a model answer, (3) one tip."
    ),
    "all": (
        "Generate {n} mixed interview questions (technical, behavioral, HR) "
        "for a {level}-level {role}. Include model answers and improvement tips."
    ),
}


def generate_questions(
    name: str,
    job_role: str,
    level: str,
    question_type: str = "all",
    num: int = 10,
    user_id: str = "anon",
    session_id: Optional[str] = None,
    ip: str = "unknown",
) -> Dict[str, Any]:
    """Generate tailored interview questions."""
    sid = session_id or _session()
    exec_id = str(uuid.uuid4())
    ops.begin(exec_id)

    # Security check
    safe, threat = sec.check(f"{name} {job_role}", user_id, ip)
    if not safe:
        ops.end(exec_id)
        return {"success": False, "error": f"Blocked: {threat}", "session_id": sid}

    tmpl = QUESTION_TEMPLATES.get(question_type, QUESTION_TEMPLATES["all"])
    query = tmpl.format(n=num, level=level, role=job_role)
    user_ctx = {"name": name, "job_role": job_role, "level": level}

    result = _guardrailed_call(query, user_ctx, sid, user_id, "question")
    ops.end(exec_id)

    return {
        "success": result["success"],
        "session_id": sid,
        "candidate": name,
        "job_role": job_role,
        "level": level,
        "question_type": question_type,
        "content": result.get("text", ""),
        "warnings": result.get("warnings", []),
        "guardrail_flags": result.get("guardrail_flags", []),
        "tokens_used": result.get("tokens", 0),
        "powered_by": "IBM Granite (mock)" if result.get("mock") else "IBM Granite",
        "error": result.get("error"),
    }


def analyze_resume(
    name: str,
    job_role: str,
    level: str,
    resume_text: str,
    user_id: str = "anon",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze resume and provide gap analysis + improvement tips."""
    sid = session_id or _session()
    query = (
        f"Analyze this resume for a {level}-level {job_role} position. "
        f"Identify: 1) Key strengths, 2) Skill gaps, 3) Top 3 improvement suggestions, "
        f"4) Interview focus areas. Resume: {resume_text[:2000]}"
    )
    user_ctx = {"name": name, "job_role": job_role, "level": level}
    result = _guardrailed_call(query, user_ctx, sid, user_id, "resume_analysis")
    return {
        "success": result["success"],
        "session_id": sid,
        "analysis": result.get("text", ""),
        "warnings": result.get("warnings", []),
        "tokens_used": result.get("tokens", 0),
        "error": result.get("error"),
    }


def evaluate_answer(
    job_role: str,
    level: str,
    question: str,
    candidate_answer: str,
    user_id: str = "anon",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate a candidate's answer and provide scored feedback."""
    sid = session_id or _session()
    query = (
        f"Evaluate this interview answer.\n"
        f"Role: {job_role} ({level} level)\n"
        f"Question: {question}\n"
        f"Answer: {candidate_answer}\n"
        f"Provide: 1) Score (1-10), 2) Strengths, 3) What to improve, 4) A better version."
    )
    user_ctx = {"job_role": job_role, "level": level}
    result = _guardrailed_call(query, user_ctx, sid, user_id, "evaluation")
    return {
        "success": result["success"],
        "session_id": sid,
        "question": question,
        "feedback": result.get("text", ""),
        "warnings": result.get("warnings", []),
        "tokens_used": result.get("tokens", 0),
        "error": result.get("error"),
    }


def create_plan(
    name: str,
    job_role: str,
    level: str,
    days: int = 14,
    user_id: str = "anon",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a day-by-day interview preparation plan."""
    sid = session_id or _session()
    query = (
        f"Create a {days}-day interview preparation plan for {name}, "
        f"a {level}-level {job_role} candidate. "
        f"Include daily tasks, study topics, mock interview schedule, and confidence tips."
    )
    user_ctx = {"name": name, "job_role": job_role, "level": level}
    result = _guardrailed_call(query, user_ctx, sid, user_id, "plan")
    text = eth.add_disclaimer(result.get("text", ""))
    return {
        "success": result["success"],
        "session_id": sid,
        "plan": text,
        "warnings": result.get("warnings", []),
        "tokens_used": result.get("tokens", 0),
        "error": result.get("error"),
    }


def full_prepare(
    name: str,
    job_role: str,
    level: str,
    resume_text: Optional[str] = None,
    days: int = 14,
    user_id: str = "anon",
    session_id: Optional[str] = None,
    ip: str = "unknown",
) -> Dict[str, Any]:
    """Complete multi-step preparation pipeline using all 5 specialist areas."""
    sid = session_id or _session()
    t0 = time.time()

    out: Dict[str, Any] = {"session_id": sid, "candidate": name, "job_role": job_role,
                            "level": level, "sections": {}}

    # Step 1: Questions (technical + behavioral)
    for qtype in ["technical", "behavioral", "hr"]:
        r = generate_questions(name, job_role, level, qtype, 4, user_id, sid, ip)
        out["sections"][f"questions_{qtype}"] = r.get("content", "")

    # Step 2: Resume analysis (if provided)
    if resume_text:
        r = analyze_resume(name, job_role, level, resume_text, user_id, sid)
        out["sections"]["resume_analysis"] = r.get("analysis", "")

    # Step 3: Preparation plan
    r = create_plan(name, job_role, level, days, user_id, sid)
    out["sections"]["preparation_plan"] = r.get("plan", "")

    out["total_latency_ms"] = int((time.time() - t0) * 1000)
    out["usage"] = ops.usage()
    out["success"] = True
    return out
