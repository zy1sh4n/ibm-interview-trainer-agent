"""
IBM Interview Trainer – Multi-Agent Orchestrator
==================================================
Coordinates the specialist agent pool to deliver a complete
interview preparation experience.

Specialist Agents:
  • QuestionGeneratorAgent    — generates tailored interview questions
  • AnswerEvaluatorAgent      — scores and critiques candidate answers
  • ResumeAnalyzerAgent       — parses resumes and matches skills to roles
  • PrepPlannerAgent          — builds day-by-day preparation plans
  • HRAdvisorAgent            — provides HR and behavioral coaching

The Orchestrator routes tasks, aggregates results, applies
multi-agent guardrails, and enforces human-in-the-loop gates.
"""

import uuid
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config.settings import get_settings
from utils.logger import get_logger, audit_log
from guardrails.multi_agent_guardrails import (
    MultiAgentGuardrails,
    AgentRole,
)
from guardrails.hitl_guardrails import HumanInTheLoopGuardrails
from guardrails.operational_guardrails import OperationalGuardrails
from guardrails.security_guardrails import SecurityGuardrails
from agents.interview_trainer_agent import (
    InterviewTrainerAgent,
    UserProfile,
    QuestionType,
    AgentResponse,
)

settings = get_settings()
logger = get_logger("multi_agent_orchestrator")


@dataclass
class OrchestrationResult:
    """Aggregated result from the multi-agent pipeline."""
    session_id: str
    success: bool
    questions: List[Dict[str, Any]] = field(default_factory=list)
    resume_analysis: Optional[Dict[str, Any]] = None
    preparation_plan: Optional[Dict[str, Any]] = None
    answer_evaluations: List[Dict[str, Any]] = field(default_factory=list)
    hr_advice: Optional[str] = None
    agent_contributions: Dict[str, str] = field(default_factory=dict)
    total_tokens_used: int = 0
    total_latency_ms: int = 0
    warnings: List[str] = field(default_factory=list)
    guardrail_flags: List[str] = field(default_factory=list)
    hitl_requests: List[str] = field(default_factory=list)
    error: Optional[str] = None


class BaseSpecialistAgent:
    """
    Lightweight wrapper used by the orchestrator to represent each
    specialist agent. All heavy AI logic lives in InterviewTrainerAgent.
    """

    def __init__(self, agent_id: str, role: AgentRole, trainer: InterviewTrainerAgent):
        self.agent_id = agent_id
        self.role = role
        self._trainer = trainer
        logger.info(f"Specialist agent ready: {agent_id} ({role.value})")


class QuestionGeneratorAgent(BaseSpecialistAgent):
    def run(self, profile: UserProfile, question_type: QuestionType, num_questions: int) -> AgentResponse:
        return self._trainer.generate_interview_questions(profile, question_type, num_questions)


class AnswerEvaluatorAgent(BaseSpecialistAgent):
    def run(self, profile: UserProfile, question: str, answer: str) -> AgentResponse:
        return self._trainer.evaluate_answer(profile, question, answer)


class ResumeAnalyzerAgent(BaseSpecialistAgent):
    def run(self, profile: UserProfile, resume_text: str) -> AgentResponse:
        return self._trainer.analyze_resume(profile, resume_text)


class PrepPlannerAgent(BaseSpecialistAgent):
    def run(self, profile: UserProfile, days: int) -> AgentResponse:
        return self._trainer.create_preparation_plan(profile, days)


class HRAdvisorAgent(BaseSpecialistAgent):
    """Provides HR-focused behavioral coaching using the trainer's RAG engine."""

    def run(self, profile: UserProfile) -> AgentResponse:
        return self._trainer.generate_interview_questions(
            profile, QuestionType.HR, num_questions=5
        )


class MultiAgentOrchestrator:
    """
    Central orchestrator that routes tasks across specialist agents,
    aggregates results, and enforces all multi-agent guardrails.
    """

    def __init__(self):
        # Shared trainer instance (single IBM Granite client)
        self._trainer = InterviewTrainerAgent()

        # Guardrails
        self._ma_guard = MultiAgentGuardrails()
        self._hitl = HumanInTheLoopGuardrails()
        self._ops_guard = OperationalGuardrails()
        self._security_guard = SecurityGuardrails()

        # Register and create specialist agents
        self._agents: Dict[AgentRole, BaseSpecialistAgent] = {}
        self._setup_agents()

        logger.info("Multi-Agent Orchestrator initialized.")

    def _setup_agents(self) -> None:
        """Register all specialist agents with the multi-agent guardrail layer."""
        specs = [
            ("agent_question_gen", AgentRole.QUESTION_GENERATOR, QuestionGeneratorAgent),
            ("agent_answer_eval", AgentRole.ANSWER_EVALUATOR, AnswerEvaluatorAgent),
            ("agent_resume", AgentRole.RESUME_ANALYZER, ResumeAnalyzerAgent),
            ("agent_prep_planner", AgentRole.PREP_PLANNER, PrepPlannerAgent),
            ("agent_hr_advisor", AgentRole.HR_ADVISOR, HRAdvisorAgent),
        ]
        for agent_id, role, AgentClass in specs:
            ok = self._ma_guard.register_agent(agent_id, role)
            if ok:
                self._agents[role] = AgentClass(agent_id, role, self._trainer)

        # Register orchestrator itself
        self._ma_guard.register_agent("agent_orchestrator", AgentRole.ORCHESTRATOR)

    # ------------------------------------------------------------------
    # Primary Orchestration Entry Point
    # ------------------------------------------------------------------

    def run_full_preparation(
        self,
        profile: UserProfile,
        resume_text: Optional[str] = None,
        answers_to_evaluate: Optional[List[Dict[str, str]]] = None,
        days_until_interview: int = 14,
        include_hr_advice: bool = True,
        ip_address: Optional[str] = None,
    ) -> OrchestrationResult:
        """
        Execute the complete interview preparation pipeline:
        1. Resume analysis (if provided)
        2. Question generation (technical + behavioral + HR)
        3. Answer evaluation (if sample answers provided)
        4. Preparation plan generation
        5. HR coaching advice
        """
        start = time.time()
        execution_id = str(uuid.uuid4())
        self._ops_guard.begin_execution(execution_id, profile.user_id, profile.session_id)

        result = OrchestrationResult(session_id=profile.session_id, success=False)

        try:
            # ----------------------------------------------------------
            # Step 1: Resume Analysis
            # ----------------------------------------------------------
            if resume_text:
                logger.info("Orchestrator → ResumeAnalyzerAgent")
                ok, _ = self._ma_guard.send_message(
                    "agent_orchestrator", "agent_resume",
                    "analyze_resume", {"user_id": profile.user_id},
                )
                if ok:
                    # Check capability
                    cap_ok, cap_msg = self._ma_guard.check_capability("agent_resume", "parse_resume")
                    if cap_ok:
                        resume_resp = self._agents[AgentRole.RESUME_ANALYZER].run(profile, resume_text)
                        if resume_resp.success:
                            result.resume_analysis = resume_resp.resume_analysis
                            result.agent_contributions["resume_analyzer"] = "completed"
                            result.total_tokens_used += resume_resp.tokens_used
                        else:
                            result.warnings.append(f"Resume analysis failed: {resume_resp.error}")

            # ----------------------------------------------------------
            # Step 2: Question Generation (3 question types in parallel logic)
            # ----------------------------------------------------------
            logger.info("Orchestrator → QuestionGeneratorAgent")
            all_questions = []

            for q_type in [QuestionType.TECHNICAL, QuestionType.BEHAVIORAL, QuestionType.HR]:
                # Loop detection fingerprint
                fingerprint = f"question_gen_{q_type.value}_{profile.job_role}"
                loop_detected, loop_msg = self._ops_guard.check_loop(execution_id, fingerprint)
                if loop_detected:
                    result.warnings.append(loop_msg)
                    break

                # Timeout check
                timed_out, timeout_msg = self._ops_guard.check_timeout(execution_id)
                if timed_out:
                    result.warnings.append(timeout_msg)
                    break

                # Token budget check
                within_budget, budget_msg = self._ops_guard.check_token_budget(
                    600, profile.session_id, execution_id
                )
                if not within_budget:
                    result.warnings.append(budget_msg)
                    break

                q_resp = self._agents[AgentRole.QUESTION_GENERATOR].run(
                    profile, q_type, num_questions=4
                )
                if q_resp.success:
                    for q in q_resp.questions:
                        all_questions.append({
                            "question_id": q.question_id,
                            "question": q.question,
                            "type": q.question_type.value,
                            "difficulty": q.difficulty,
                            "model_answer": q.model_answer,
                            "tips": q.improvement_tips,
                            "follow_ups": q.follow_up_questions,
                        })
                    result.total_tokens_used += q_resp.tokens_used
                else:
                    result.guardrail_flags.extend(q_resp.guardrail_flags)

            result.questions = all_questions
            result.agent_contributions["question_generator"] = f"{len(all_questions)} questions"

            # ----------------------------------------------------------
            # Step 3: Answer Evaluation
            # ----------------------------------------------------------
            if answers_to_evaluate:
                logger.info("Orchestrator → AnswerEvaluatorAgent")
                for item in answers_to_evaluate[:5]:  # limit to 5 evaluations
                    eval_resp = self._agents[AgentRole.ANSWER_EVALUATOR].run(
                        profile,
                        question=item.get("question", ""),
                        answer=item.get("answer", ""),
                    )
                    if eval_resp.success and eval_resp.answer_evaluation:
                        result.answer_evaluations.append(eval_resp.answer_evaluation)
                        result.total_tokens_used += eval_resp.tokens_used
                result.agent_contributions["answer_evaluator"] = (
                    f"{len(result.answer_evaluations)} evaluations"
                )

            # ----------------------------------------------------------
            # Step 4: Preparation Plan
            # ----------------------------------------------------------
            logger.info("Orchestrator → PrepPlannerAgent")
            plan_resp = self._agents[AgentRole.PREP_PLANNER].run(profile, days_until_interview)
            if plan_resp.success:
                result.preparation_plan = plan_resp.preparation_plan
                result.total_tokens_used += plan_resp.tokens_used
                result.agent_contributions["prep_planner"] = "plan_created"

            # ----------------------------------------------------------
            # Step 5: HR Advice
            # ----------------------------------------------------------
            if include_hr_advice:
                logger.info("Orchestrator → HRAdvisorAgent")
                hr_resp = self._agents[AgentRole.HR_ADVISOR].run(profile)
                if hr_resp.success and hr_resp.questions:
                    hr_questions = "\n".join(
                        f"• {q.question}" for q in hr_resp.questions[:3]
                    )
                    result.hr_advice = (
                        f"Top HR Questions for {profile.job_role}:\n{hr_questions}"
                    )
                    result.total_tokens_used += hr_resp.tokens_used
                    result.agent_contributions["hr_advisor"] = "advice_provided"

            # ----------------------------------------------------------
            # HITL Gate: Critical output review for senior roles
            # ----------------------------------------------------------
            if profile.experience_level.value in ("senior", "executive"):
                hitl_req = self._hitl.request_approval(
                    action_type="generate_interview_questions",
                    description=(
                        f"Senior-level interview prep for {profile.name} "
                        f"targeting {profile.job_role}"
                    ),
                    payload={"session_id": profile.session_id, "questions_count": len(all_questions)},
                    requested_by=profile.user_id,
                    session_id=profile.session_id,
                    risk_level="low",
                )
                result.hitl_requests.append(hitl_req.request_id)

            # ----------------------------------------------------------
            # Finalize
            # ----------------------------------------------------------
            result.total_latency_ms = int((time.time() - start) * 1000)
            result.success = True

            self._ops_guard.record_token_usage(
                result.total_tokens_used, profile.user_id, profile.session_id, execution_id
            )
            self._ops_guard.end_execution(execution_id, "completed")

            # Aggregate warnings from all agents
            audit_log(
                event_type="orchestration_complete",
                user_id=profile.user_id,
                session_id=profile.session_id,
                action="full_preparation_pipeline",
                details={
                    "questions": len(result.questions),
                    "tokens": result.total_tokens_used,
                    "latency_ms": result.total_latency_ms,
                    "agents": list(result.agent_contributions.keys()),
                },
            )

            logger.info(
                f"Orchestration complete: {len(result.questions)} questions, "
                f"{result.total_tokens_used} tokens, {result.total_latency_ms}ms"
            )

        except Exception as exc:
            logger.error(f"Orchestration error: {exc}", exc_info=True)
            self._ops_guard.end_execution(execution_id, "error")
            result.error = str(exc)
            result.success = False

        return result

    def get_agent_status(self) -> Dict[str, Any]:
        """Return registered agent info and communication log summary."""
        return {
            "registered_agents": [
                {"agent_id": a.agent_id, "role": a.role.value}
                for a in self._agents.values()
            ],
            "message_log_count": len(self._ma_guard.get_communication_log()),
            "pending_hitl_approvals": len(self._hitl.get_pending_requests()),
            "usage_report": self._ops_guard.get_usage_report(),
        }
