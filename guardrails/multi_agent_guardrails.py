"""Guardrail 8 – Multi-Agent · ACL · task validation · conflict resolution · loop prevention"""
import uuid, logging
from typing import Any, Dict, List, Optional, Set, Tuple
from config.settings import get_settings

log = logging.getLogger("guard.multiagent")
cfg = get_settings()

ROLES = {"orchestrator", "question_generator", "answer_evaluator", "resume_analyzer",
         "prep_planner", "hr_advisor"}

CAPABILITIES: Dict[str, Set[str]] = {
    "orchestrator":        {"delegate", "aggregate", "read_ctx", "write_ctx"},
    "question_generator":  {"search_kb", "generate_questions", "read_ctx"},
    "answer_evaluator":    {"evaluate", "score", "feedback", "read_ctx"},
    "resume_analyzer":     {"parse_resume", "extract_skills", "read_ctx"},
    "prep_planner":        {"create_plan", "schedule", "read_ctx", "write_ctx"},
    "hr_advisor":          {"hr_guidance", "behavioral_coaching", "read_ctx"},
}

_agents: Dict[str, str] = {}          # agent_id -> role
_messages: List[Dict] = []
_handoffs: Dict[str, int] = {}


def register(agent_id: str, role: str) -> bool:
    # Idempotent: already registered with same role → skip silently
    if agent_id in _agents:
        return True
    # max_agents check excludes already-registered agents
    if len(_agents) >= cfg.max_agents:
        log.warning(f"Max agents ({cfg.max_agents}) reached, skipping {agent_id}")
        return False
    if role not in ROLES:
        log.error(f"Unknown role: {role}")
        return False
    _agents[agent_id] = role
    log.info(f"Agent registered: {agent_id} as {role}")
    return True


def can(agent_id: str, capability: str) -> Tuple[bool, str]:
    role = _agents.get(agent_id)
    if not role:
        return False, f"Agent '{agent_id}' not registered"
    if capability not in CAPABILITIES.get(role, set()):
        return False, f"Agent '{agent_id}' ({role}) lacks capability '{capability}'"
    return True, "ok"


def send(sender: str, recipient: str, task: str, payload: Dict) -> Tuple[bool, Dict]:
    if sender not in _agents or recipient not in _agents:
        return False, {"error": "Unknown agent"}
    key = f"{sender}->{recipient}"
    _handoffs[key] = _handoffs.get(key, 0) + 1
    if _handoffs[key] > cfg.max_handoffs:
        log.error(f"Handoff limit exceeded: {key}")
        return False, {"error": "Handoff limit exceeded"}
    msg = {"id": str(uuid.uuid4()), "from": sender, "to": recipient,
           "task": task, "payload": payload}
    _messages.append(msg)
    return True, msg


def resolve_conflict(outputs: Dict[str, Any], strategy: str = "first") -> Any:
    """Resolve conflicting agent outputs. Strategies: first | majority."""
    if not outputs:
        return None
    if strategy == "majority":
        from collections import Counter
        counts = Counter(str(v) for v in outputs.values())
        winner = counts.most_common(1)[0][0]
        return next(v for v in outputs.values() if str(v) == winner)
    return next(iter(outputs.values()))


def message_log() -> List[Dict]:
    return [{"id": m["id"], "from": m["from"], "to": m["to"], "task": m["task"]} for m in _messages]
