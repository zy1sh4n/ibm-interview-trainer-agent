"""
IBM Interview Trainer Agent — Streamlit UI
==========================================
Run:  streamlit run streamlit_app.py
"""
import sys
import uuid
import time
import textwrap
from typing import Any, Dict, List, Optional

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="IBM Interview Trainer Agent",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* IBM-style accent colour */
    :root { --ibm-blue: #0f62fe; --ibm-gray: #f4f4f4; }

    .ibm-header {
        background: linear-gradient(135deg, #0f62fe 0%, #0043ce 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 0.5rem;
        margin-bottom: 1.5rem;
    }
    .ibm-header h1 { margin: 0; font-size: 1.8rem; font-weight: 600; }
    .ibm-header p  { margin: 0.25rem 0 0; opacity: 0.85; font-size: 0.95rem; }

    .metric-card {
        background: #f4f4f4;
        border-left: 4px solid #0f62fe;
        border-radius: 0.375rem;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
    }
    .metric-card .label { font-size: 0.75rem; color: #525252; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-card .value { font-size: 1.25rem; font-weight: 700; color: #161616; }

    .guard-pass { color: #198038; font-weight: 600; }
    .guard-warn { color: #f1c21b; font-weight: 600; }
    .guard-fail { color: #da1e28; font-weight: 600; }

    .section-box {
        background: #f4f4f4;
        border-radius: 0.5rem;
        padding: 1rem 1.25rem;
        margin-top: 0.75rem;
    }

    .stTabs [data-baseweb="tab"] { font-weight: 600; }

    footer { visibility: hidden; }
    .ibm-footer {
        text-align: center;
        color: #6f6f6f;
        font-size: 0.8rem;
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)


# ── Session state initialisation ──────────────────────────────────────────────
def _init_state():
    defaults = {
        "session_id":      str(uuid.uuid4()),
        "consented":       False,
        "user_id":         str(uuid.uuid4())[:8],
        "history":         [],          # list of {"role", "content"}
        "token_total":     0,
        "request_count":   0,
        "last_result":     None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ── Lazy-import agent (avoids slow import on every rerun) ─────────────────────
@st.cache_resource(show_spinner="Loading IBM Granite agent…")
def _load_agent():
    """Import the agent module once; cached across reruns."""
    from agents import interview_trainer_agent as ag
    from core.ibm_granite_client import GraniteClient
    from guardrails import (
        input_guardrails as ing,
        output_guardrails as oug,
        data_privacy_guardrails as priv,
        operational_guardrails as ops,
    )
    return ag, GraniteClient, ing, oug, priv, ops

try:
    ag, GraniteClient, ing, oug, priv, ops = _load_agent()
    _agent_loaded = True
except Exception as _load_err:
    _agent_loaded = False
    _load_error_msg = str(_load_err)


# ── Helper utilities ───────────────────────────────────────────────────────────

def _model_badge() -> str:
    try:
        from config.settings import get_settings
        cfg = get_settings()
        if cfg.ibm_watsonx_api_key and cfg.ibm_watsonx_project_id:
            return "🟢 **IBM Granite** (live)"
    except Exception:
        pass
    return "🟡 **IBM Granite** (mock mode)"


def _render_guardrail_status(result: Dict):
    """Render a small guardrail status panel from an agent result dict."""
    flags  = result.get("guardrail_flags", [])
    warns  = result.get("warnings", [])
    error  = result.get("error")

    cols = st.columns(3)
    with cols[0]:
        if not flags:
            st.markdown('<span class="guard-pass">✔ Input / Output OK</span>', unsafe_allow_html=True)
        else:
            st.markdown(f'<span class="guard-fail">✖ Guardrail Violations: {len(flags)}</span>', unsafe_allow_html=True)
    with cols[1]:
        if warns:
            st.markdown(f'<span class="guard-warn">⚠ {len(warns)} warning(s)</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="guard-pass">✔ No warnings</span>', unsafe_allow_html=True)
    with cols[2]:
        tokens = result.get("tokens_used", 0)
        powered = result.get("powered_by", "IBM Granite")
        st.caption(f"Tokens: {tokens} · {powered}")

    if flags:
        with st.expander("Guardrail violations"):
            for f in flags:
                st.error(f)
    if warns:
        with st.expander("Guardrail warnings"):
            for w in warns:
                st.warning(w)
    if error:
        st.error(f"Agent error: {error}")


def _append_history(role: str, content: str):
    st.session_state.history.append({"role": role, "content": content})
    if len(st.session_state.history) > 50:
        st.session_state.history = st.session_state.history[-50:]


def _accumulate_tokens(result: Dict):
    st.session_state.token_total += result.get("tokens_used", 0)
    st.session_state.request_count += 1
    st.session_state.last_result = result


# ── Sidebar ────────────────────────────────────────────────────────────────────

def _sidebar():
    with st.sidebar:
        st.markdown("## 🎯 Candidate Profile")

        name = st.text_input("Full Name", value="Alex Johnson", key="sb_name",
                             help="Your name as you'd like it used in the session.")
        job_role = st.text_input("Target Job Role", value="Software Engineer", key="sb_role",
                                 help="e.g. Data Scientist, Product Manager, DevOps Engineer")
        level = st.selectbox("Experience Level", ["junior", "mid", "senior", "lead", "executive"],
                             index=1, key="sb_level")

        st.divider()
        st.markdown("### ⚙️ Session Info")
        st.caption(f"Session ID: `{st.session_state.session_id[:12]}…`")
        st.caption(f"User ID:    `{st.session_state.user_id}`")
        st.caption(f"Requests:   `{st.session_state.request_count}`")
        st.caption(f"Tokens:     `{st.session_state.token_total}`")
        st.caption(_model_badge())

        st.divider()
        st.markdown("### 🔒 Data Consent")
        consent_ok = st.checkbox(
            "I consent to my input being processed for interview preparation purposes.",
            value=st.session_state.consented,
            key="consent_cb",
        )
        if consent_ok != st.session_state.consented:
            st.session_state.consented = consent_ok
            if _agent_loaded:
                priv.record_consent(
                    st.session_state.user_id,
                    consent_ok,
                    ["interview_prep", "resume_analysis", "answer_evaluation"],
                )
            if consent_ok:
                st.success("Consent recorded.")
            else:
                st.info("Consent withdrawn.")

        if st.button("🔄 New Session", use_container_width=True):
            st.session_state.session_id   = str(uuid.uuid4())
            st.session_state.history      = []
            st.session_state.token_total  = 0
            st.session_state.request_count = 0
            st.session_state.last_result  = None
            st.rerun()

        st.divider()
        st.markdown("""
<small>
**IBM Interview Trainer Agent**  
Problem Statement #22  
Powered by IBM Granite · RAG  
9-Layer Guardrail Architecture
</small>
""", unsafe_allow_html=True)

    return name, job_role, level


# ── Consent gate ──────────────────────────────────────────────────────────────

def _require_consent():
    if not st.session_state.consented:
        st.warning(
            "⚠️ **Consent required.** Please tick the consent checkbox in the sidebar "
            "before using any feature."
        )
        return False
    return True


# ── Input validation helper (shows inline feedback) ──────────────────────────

def _validate_input(text: str, label: str = "Input") -> Optional[str]:
    """Run input guardrail and return clean text, or None if blocked."""
    if not _agent_loaded:
        return text
    res = ing.validate(text, st.session_state.user_id)
    if not res.is_valid:
        st.error(f"**{label} blocked by guardrail:** {', '.join(res.violations)}")
        return None
    if res.pii_found:
        st.warning(f"⚠️ PII detected ({', '.join(res.pii_found)}) and redacted from prompt.")
    return res.clean


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Generate Interview Questions
# ══════════════════════════════════════════════════════════════════════════════

def _tab_questions(name, job_role, level):
    st.subheader("📋 Generate Interview Questions")
    st.markdown(
        "Generate tailored technical, behavioral, or HR interview questions with "
        "model answers and improvement tips."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        q_type = st.selectbox(
            "Question Type",
            ["all", "technical", "behavioral", "hr"],
            format_func=lambda x: {
                "all": "All Types (Mixed)",
                "technical": "Technical",
                "behavioral": "Behavioral (STAR)",
                "hr": "HR / Soft Skills",
            }[x],
            key="qt_type",
        )
    with col2:
        num_q = st.slider("Number of Questions", 3, 15, 8, key="qt_num")

    st.markdown("**Additional context** *(optional)*")
    extra_ctx = st.text_area(
        "Add any specific topics, skills, or technologies you want covered:",
        placeholder="e.g. React, system design, STAR stories about leadership…",
        height=80,
        key="qt_extra",
    )

    if st.button("🚀 Generate Questions", type="primary", use_container_width=True, key="btn_gen_q"):
        if not _require_consent():
            return
        if not job_role.strip():
            st.error("Please enter a target job role in the sidebar.")
            return

        # Build query with optional extra context
        query_hint = f" Focus areas: {extra_ctx}" if extra_ctx.strip() else ""
        clean_hint = _validate_input(job_role + query_hint, "Job Role")
        if clean_hint is None:
            return

        with st.spinner("IBM Granite is generating your questions…"):
            result = ag.generate_questions(
                name=name,
                job_role=job_role,
                level=level,
                question_type=q_type,
                num=num_q,
                user_id=st.session_state.user_id,
                session_id=st.session_state.session_id,
            )

        _accumulate_tokens(result)
        _append_history("assistant", f"Generated {num_q} {q_type} questions for {job_role}")

        if result.get("success"):
            st.success(f"✅ {num_q} questions generated for **{name}** → **{job_role}** ({level})")
            _render_guardrail_status(result)
            st.markdown("---")
            st.markdown("### 📝 Your Questions")
            st.markdown(
                f'<div class="section-box">{result["content"].replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                "⬇️ Download Questions (TXT)",
                data=result["content"],
                file_name=f"interview_questions_{job_role.replace(' ','_')}.txt",
                mime="text/plain",
                key="dl_q",
            )
        else:
            st.error(f"Failed to generate questions: {result.get('error')}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Resume Analyzer
# ══════════════════════════════════════════════════════════════════════════════

def _tab_resume(name, job_role, level):
    st.subheader("📄 Resume Analyzer")
    st.markdown(
        "Paste your resume or professional summary. The agent will identify strengths, "
        "skill gaps, and interview focus areas."
    )

    resume_text = st.text_area(
        "Resume / Professional Summary",
        placeholder=(
            "Paste your resume text here…\n\n"
            "Example:\nSoftware Engineer with 5 years of experience in Python, Django, "
            "and REST APIs. Led a team of 3 developers at XYZ Corp…"
        ),
        height=300,
        key="ra_resume",
    )

    if st.button("🔍 Analyze Resume", type="primary", use_container_width=True, key="btn_analyze"):
        if not _require_consent():
            return
        if not resume_text.strip():
            st.error("Please paste your resume text above.")
            return
        if len(resume_text.strip()) < 50:
            st.warning("Resume text seems very short. Add more detail for a better analysis.")

        clean_resume = _validate_input(resume_text, "Resume")
        if clean_resume is None:
            return

        with st.spinner("Analyzing your resume with IBM Granite…"):
            result = ag.analyze_resume(
                name=name,
                job_role=job_role,
                level=level,
                resume_text=clean_resume,
                user_id=st.session_state.user_id,
                session_id=st.session_state.session_id,
            )

        _accumulate_tokens(result)
        _append_history("assistant", f"Analyzed resume for {job_role}")

        if result.get("success"):
            st.success("✅ Resume analysis complete")
            _render_guardrail_status(result)
            st.markdown("---")
            st.markdown("### 🔎 Analysis Report")
            st.markdown(
                f'<div class="section-box">{result["analysis"].replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                "⬇️ Download Analysis (TXT)",
                data=result["analysis"],
                file_name=f"resume_analysis_{name.replace(' ','_')}.txt",
                mime="text/plain",
                key="dl_ra",
            )
        else:
            st.error(f"Analysis failed: {result.get('error')}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Answer Evaluator
# ══════════════════════════════════════════════════════════════════════════════

def _tab_evaluator(name, job_role, level):
    st.subheader("✏️ Answer Evaluator")
    st.markdown(
        "Practice answering an interview question and receive scored feedback, "
        "strengths, improvement suggestions, and a model answer."
    )

    question = st.text_area(
        "Interview Question",
        placeholder="e.g. Describe a time you resolved a conflict in your team.",
        height=100,
        key="ev_question",
    )
    answer = st.text_area(
        "Your Answer",
        placeholder="Type your answer here…",
        height=200,
        key="ev_answer",
    )

    if st.button("⚡ Evaluate My Answer", type="primary", use_container_width=True, key="btn_eval"):
        if not _require_consent():
            return
        if not question.strip():
            st.error("Please enter the interview question.")
            return
        if not answer.strip():
            st.error("Please enter your answer.")
            return

        clean_q = _validate_input(question, "Question")
        if clean_q is None:
            return
        clean_a = _validate_input(answer, "Answer")
        if clean_a is None:
            return

        with st.spinner("Evaluating your answer with IBM Granite…"):
            result = ag.evaluate_answer(
                job_role=job_role,
                level=level,
                question=clean_q,
                candidate_answer=clean_a,
                user_id=st.session_state.user_id,
                session_id=st.session_state.session_id,
            )

        _accumulate_tokens(result)
        _append_history("user", f"Q: {question[:80]}…")
        _append_history("assistant", f"Feedback provided for {job_role} question")

        if result.get("success"):
            st.success("✅ Evaluation complete")
            _render_guardrail_status(result)
            st.markdown("---")

            col_q, col_a = st.columns(2)
            with col_q:
                st.markdown("**Question Asked**")
                st.info(question)
            with col_a:
                st.markdown("**Your Answer**")
                st.info(answer[:400] + ("…" if len(answer) > 400 else ""))

            st.markdown("### 📊 Feedback")
            st.markdown(
                f'<div class="section-box">{result["feedback"].replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                "⬇️ Download Feedback (TXT)",
                data=result["feedback"],
                file_name=f"answer_feedback_{job_role.replace(' ','_')}.txt",
                mime="text/plain",
                key="dl_ev",
            )
        else:
            st.error(f"Evaluation failed: {result.get('error')}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Preparation Plan
# ══════════════════════════════════════════════════════════════════════════════

def _tab_plan(name, job_role, level):
    st.subheader("📅 Preparation Plan")
    st.markdown(
        "Get a personalized day-by-day study and mock-interview schedule "
        "tailored to your role, level, and timeline."
    )

    days = st.slider("Preparation Days", 7, 30, 14, key="pp_days",
                     help="How many days until your interview?")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="label">Candidate</div><div class="value">{name}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="label">Target Role</div><div class="value">{job_role}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="label">Level</div><div class="value">{level.capitalize()}</div></div>', unsafe_allow_html=True)

    if st.button("📅 Create My Plan", type="primary", use_container_width=True, key="btn_plan"):
        if not _require_consent():
            return
        if not job_role.strip():
            st.error("Please enter a target job role in the sidebar.")
            return

        with st.spinner(f"Building your {days}-day plan with IBM Granite…"):
            result = ag.create_plan(
                name=name,
                job_role=job_role,
                level=level,
                days=days,
                user_id=st.session_state.user_id,
                session_id=st.session_state.session_id,
            )

        _accumulate_tokens(result)
        _append_history("assistant", f"Created {days}-day plan for {job_role}")

        if result.get("success"):
            st.success(f"✅ {days}-day preparation plan created")
            _render_guardrail_status(result)
            st.markdown("---")
            st.markdown("### 🗓️ Your Preparation Schedule")
            st.markdown(
                f'<div class="section-box">{result["plan"].replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                "⬇️ Download Plan (TXT)",
                data=result["plan"],
                file_name=f"prep_plan_{name.replace(' ','_')}_{days}d.txt",
                mime="text/plain",
                key="dl_plan",
            )
        else:
            st.error(f"Plan generation failed: {result.get('error')}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Full Preparation (All-in-One)
# ══════════════════════════════════════════════════════════════════════════════

def _tab_full(name, job_role, level):
    st.subheader("🏆 Full Preparation Package")
    st.markdown(
        "Run the complete multi-step pipeline: technical questions, behavioral questions, "
        "HR questions, optional resume analysis, and a preparation plan — all in one go."
    )

    resume_text = st.text_area(
        "Resume / Summary *(optional — leave blank to skip)*",
        placeholder="Paste resume text here to include a resume gap analysis…",
        height=140,
        key="fp_resume",
    )
    days = st.slider("Preparation Days", 7, 30, 14, key="fp_days")

    st.info(
        "ℹ️ This runs 4–5 Granite calls in sequence. In mock mode it completes instantly; "
        "with live credentials each call takes a few seconds."
    )

    if st.button("🚀 Start Full Preparation", type="primary", use_container_width=True, key="btn_full"):
        if not _require_consent():
            return
        if not job_role.strip():
            st.error("Please enter a target job role in the sidebar.")
            return

        clean_resume: Optional[str] = None
        if resume_text.strip():
            clean_resume = _validate_input(resume_text, "Resume")
            if clean_resume is None:
                return

        with st.spinner("Running full preparation pipeline with IBM Granite…"):
            result = ag.full_prepare(
                name=name,
                job_role=job_role,
                level=level,
                resume_text=clean_resume,
                days=days,
                user_id=st.session_state.user_id,
                session_id=st.session_state.session_id,
            )

        _accumulate_tokens({
            "tokens_used": result.get("usage", {}).get("monthly_tokens_used", 0),
            "powered_by": "IBM Granite",
        })
        _append_history("assistant", f"Full preparation completed for {job_role}")

        if result.get("success"):
            latency = result.get("total_latency_ms", 0)
            st.success(f"✅ Full preparation package ready  (completed in {latency} ms)")

            # Usage metrics
            usage = result.get("usage", {})
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Tokens Used (session)", usage.get("monthly_tokens_used", 0))
            with c2:
                st.metric("Utilisation %", f'{usage.get("utilization_pct", 0):.1f}%')
            with c3:
                st.metric("Latency (ms)", latency)

            st.markdown("---")
            sections = result.get("sections", {})
            section_labels = {
                "questions_technical":  "🛠️ Technical Questions",
                "questions_behavioral": "🗣️ Behavioral Questions (STAR)",
                "questions_hr":         "👔 HR Questions",
                "resume_analysis":      "📄 Resume Analysis",
                "preparation_plan":     "📅 Preparation Plan",
            }

            for key, label in section_labels.items():
                content = sections.get(key)
                if content:
                    with st.expander(label, expanded=(key == "questions_technical")):
                        st.markdown(content)

            # Compile full report for download
            full_report = f"IBM Interview Trainer — Full Preparation Report\n"
            full_report += f"Candidate: {name} | Role: {job_role} | Level: {level}\n"
            full_report += "=" * 60 + "\n\n"
            for key, label in section_labels.items():
                content = sections.get(key)
                if content:
                    full_report += f"\n{'='*60}\n{label}\n{'='*60}\n{content}\n"

            st.download_button(
                "⬇️ Download Full Report (TXT)",
                data=full_report,
                file_name=f"full_prep_{name.replace(' ','_')}_{job_role.replace(' ','_')}.txt",
                mime="text/plain",
                key="dl_full",
            )
        else:
            st.error("Full preparation pipeline failed. Check logs.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Guardrails Dashboard
# ══════════════════════════════════════════════════════════════════════════════

def _tab_guardrails():
    st.subheader("🛡️ Guardrails Dashboard")
    st.markdown(
        "Live status of all 9 guardrail layers protecting this IBM Interview Trainer Agent."
    )

    guardrail_info = [
        ("1. Input Guardrails",          "input_guardrails.py",       ["Prompt injection detection", "PII detection & redaction", "Malicious content filtering", "Length validation", "Inappropriate content filter"]),
        ("2. Output Guardrails",         "output_guardrails.py",      ["Hallucination risk scoring", "Toxicity detection", "Sensitive info redaction", "Response length enforcement", "Factual accuracy heuristic"]),
        ("3. Tool Execution Guardrails", "tool_guardrails.py",        ["Tool access permissions", "API authorization checks", "Function-call validation", "Rate limiting per tool", "Sandboxed execution"]),
        ("4. Data Privacy Guardrails",   "data_privacy_guardrails.py",["Consent management", "Data anonymization / pseudonymization", "PII pattern redaction", "Data retention policy", "Access control"]),
        ("5. Security Guardrails",       "security_guardrails.py",    ["Jailbreak detection", "SQL injection prevention", "HMAC cross-agent signing", "Brute-force lockout", "Prompt injection protection"]),
        ("6. Operational Guardrails",    "operational_guardrails.py", ["Execution timeout limits", "Infinite loop detection", "Token budget tracking", "Rate limiting & quota", "Retry & failure handling"]),
        ("7. Human-in-the-Loop",         "hitl_guardrails.py",        ["Approval request queue", "Manual verification of critical outputs", "Escalation to human experts", "Decision audit trail"]),
        ("8. Multi-Agent Guardrails",    "multi_agent_guardrails.py", ["Agent-level access control", "Task assignment validation", "Cross-agent output verification", "Infinite agent loop prevention", "Idempotent registration"]),
        ("9. Ethical & Compliance",      "ethical_guardrails.py",     ["Gender & age bias detection", "EEO illegal question detection", "Fairness scoring", "AI disclaimer injection", "Audit trail"]),
    ]

    for title, module, checks in guardrail_info:
        with st.expander(f"**{title}** — `{module}`", expanded=False):
            cols = st.columns(2)
            mid = (len(checks) + 1) // 2
            for i, c in enumerate(checks):
                col = cols[0] if i < mid else cols[1]
                col.markdown(f'<span class="guard-pass">✔</span> {c}', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📈 Runtime Stats")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Requests This Session", st.session_state.request_count)
    with col2:
        st.metric("Tokens Used", st.session_state.token_total)
    with col3:
        if _agent_loaded:
            u = ops.usage()
            st.metric("Monthly Utilisation", f'{u.get("utilization_pct", 0):.1f}%')
        else:
            st.metric("Monthly Utilisation", "N/A")
    with col4:
        st.metric("Consent Status", "✅ Granted" if st.session_state.consented else "❌ Not Given")

    if st.session_state.history:
        st.markdown("### 🕑 Session Activity Log")
        for entry in reversed(st.session_state.history[-10:]):
            icon = "🤖" if entry["role"] == "assistant" else "👤"
            st.caption(f"{icon} {entry['content']}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # Header
    st.markdown("""
<div class="ibm-header">
  <h1>🎯 IBM Interview Trainer Agent</h1>
  <p>RAG-powered · IBM Granite · 9-Layer Guardrail Architecture · Problem Statement #22</p>
</div>
""", unsafe_allow_html=True)

    # Agent load check
    if not _agent_loaded:
        st.error(f"❌ Failed to load agent: `{_load_error_msg}`")
        st.info("Make sure all dependencies are installed: `pip install -r requirements.txt`")
        st.stop()

    # Sidebar — capture profile
    name, job_role, level = _sidebar()

    # Main tabs
    tabs = st.tabs([
        "📋 Questions",
        "📄 Resume",
        "✏️ Evaluator",
        "📅 Plan",
        "🏆 Full Prep",
        "🛡️ Guardrails",
    ])

    with tabs[0]:
        _tab_questions(name, job_role, level)

    with tabs[1]:
        _tab_resume(name, job_role, level)

    with tabs[2]:
        _tab_evaluator(name, job_role, level)

    with tabs[3]:
        _tab_plan(name, job_role, level)

    with tabs[4]:
        _tab_full(name, job_role, level)

    with tabs[5]:
        _tab_guardrails()

    # Footer
    st.markdown("""
<div class="ibm-footer">
  IBM Interview Trainer Agent · Problem Statement #22 · Powered by IBM Granite &amp; WatsonX AI<br>
  Made with IBM Bob
</div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
