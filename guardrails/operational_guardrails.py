"""Guardrail 6 – Operational · timeout · loop detection · token budget · retry"""
import time, logging
from collections import defaultdict
from typing import Any, Callable, Dict, Optional, Tuple
from config.settings import get_settings

log = logging.getLogger("guard.ops")
cfg = get_settings()

_session_tokens: Dict[str, int] = defaultdict(int)
_monthly_tokens: int = 0
_exec_start: Dict[str, float] = {}
_iterations: Dict[str, int] = defaultdict(int)
_fingerprints: Dict[str, list] = defaultdict(list)


def begin(exec_id: str):
    _exec_start[exec_id] = time.time()
    _iterations[exec_id] = 0


def end(exec_id: str):
    _exec_start.pop(exec_id, None)
    _iterations.pop(exec_id, None)
    _fingerprints.pop(exec_id, None)


def timed_out(exec_id: str) -> Tuple[bool, str]:
    start = _exec_start.get(exec_id)
    if start and time.time() - start > cfg.execution_timeout:
        return True, f"Execution timed out after {cfg.execution_timeout}s"
    return False, ""


def loop_detected(exec_id: str, fingerprint: str) -> Tuple[bool, str]:
    _iterations[exec_id] += 1
    if _iterations[exec_id] > cfg.max_iterations:
        return True, f"Max iterations ({cfg.max_iterations}) exceeded"
    if fingerprint in _fingerprints[exec_id]:
        return True, f"Repeated step detected: {fingerprint[:30]}"
    _fingerprints[exec_id].append(fingerprint)
    return False, ""


def budget_ok(tokens: int, session_id: str = "") -> Tuple[bool, str]:
    global _monthly_tokens
    if tokens > cfg.max_tokens_per_request:
        return False, f"Exceeds per-request limit ({cfg.max_tokens_per_request})"
    if session_id and _session_tokens[session_id] + tokens > cfg.max_tokens_per_session:
        return False, f"Session token budget exceeded ({cfg.max_tokens_per_session})"
    if _monthly_tokens + tokens > cfg.monthly_token_budget:
        return False, f"Monthly token budget exhausted ({cfg.monthly_token_budget})"
    return True, ""


def record_tokens(tokens: int, session_id: str = ""):
    global _monthly_tokens
    _monthly_tokens += tokens
    if session_id:
        _session_tokens[session_id] += tokens


def with_retry(fn: Callable, *args, **kwargs) -> Any:
    last = None
    for i in range(1, cfg.max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last = e
            log.warning(f"Retry {i}/{cfg.max_retries}: {e}")
            time.sleep(2 ** i)
    raise last


def usage() -> Dict:
    return {
        "monthly_tokens_used": _monthly_tokens,
        "monthly_token_budget": cfg.monthly_token_budget,
        "utilization_pct": round(100 * _monthly_tokens / cfg.monthly_token_budget, 2),
    }
