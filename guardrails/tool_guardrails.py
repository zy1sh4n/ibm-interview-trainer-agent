"""Guardrail 3 – Tool Execution · Allowlist · rate limit · timeout sandbox"""
import time, threading, logging
from collections import defaultdict, deque
from typing import Any, Callable, Dict, Optional, Tuple
from config.settings import get_settings

log = logging.getLogger("guard.tool")
cfg = get_settings()

ALLOWED_TOOLS = {
    "search_questions", "generate_answer", "analyze_resume",
    "evaluate_answer", "create_plan", "get_hr_advice",
}
DENIED_TOOLS = {"shell_command", "execute_code", "file_write", "db_delete"}

_calls: Dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def _rate_ok(key: str) -> bool:
    now = time.time()
    with _lock:
        dq = _calls[key]
        while dq and dq[0] < now - 60:
            dq.popleft()
        if len(dq) >= cfg.rate_limit_rpm:
            return False
        dq.append(now)
        return True


def execute(tool: str, params: Dict, fn: Callable, user_id: str = "anon") -> Dict[str, Any]:
    """Validate + sandbox-execute a tool call. Returns {success, result, error}."""
    if tool in DENIED_TOOLS:
        return {"success": False, "error": f"Tool '{tool}' is denied by policy."}
    if tool not in ALLOWED_TOOLS:
        return {"success": False, "error": f"Tool '{tool}' not in allowlist."}
    if not _rate_ok(user_id):
        return {"success": False, "error": "Rate limit exceeded. Try again later."}

    box: Dict[str, Any] = {"result": None, "error": None}

    def _run():
        try:
            box["result"] = fn(**params)
        except Exception as e:
            box["error"] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=cfg.execution_timeout)
    if t.is_alive():
        return {"success": False, "error": f"Tool '{tool}' timed out after {cfg.execution_timeout}s."}
    if box["error"]:
        return {"success": False, "error": box["error"]}
    return {"success": True, "result": box["result"]}
