"""Guardrail 5 – Security · jailbreak · SQL injection · HMAC · lockout"""
import re, hmac, hashlib, time, logging
from collections import defaultdict
from typing import Dict, List, Tuple
from config.settings import get_settings

log = logging.getLogger("guard.security")
cfg = get_settings()

JAILBREAK_RE = [re.compile(p, re.I | re.S) for p in [
    r"jailbreak", r"developer\s+mode", r"sudo\s+mode", r"god\s+mode",
    r"no\s+restrictions", r"unrestricted\s+(mode|access|ai)",
    r"pretend\s+you\s+have\s+no\s+(ethics|guidelines|rules)",
    r"ignore\s+(your\s+)?(training|programming|instructions)",
    r"roleplay\s+as\s+(an?\s+)?(?:evil|unrestricted|dangerous)\s+ai",
]]
SQL_RE = [re.compile(p, re.I) for p in [
    r"(\bOR\b|\bAND\b)\s+\d+\s*=\s*\d+",
    r"'?\s*;\s*(DROP|DELETE|INSERT|UPDATE|ALTER)\b",
    r"\bUNION\b.*\bSELECT\b",
    r"\bxp_cmdshell\b",
]]

_failed: Dict[str, List[float]] = defaultdict(list)


def check(content: str, user_id: str = "anon", ip: str = "unknown",
          user_agent: str = "") -> Tuple[bool, str]:
    """Return (is_safe, threat_description). Empty string = safe."""
    key = ip or user_id

    # Lockout
    window = cfg.lockout_minutes * 60
    recent = [t for t in _failed[key] if t > time.time() - window]
    if len(recent) >= cfg.max_failed_attempts:
        return False, "brute_force: account temporarily locked"

    # Jailbreak
    if cfg.jailbreak_detection:
        for r in JAILBREAK_RE:
            if r.search(content):
                _record_fail(key)
                return False, "jailbreak_attempt"

    # SQL injection
    for r in SQL_RE:
        if r.search(content):
            _record_fail(key)
            return False, "sql_injection"

    return True, ""


def _record_fail(key: str):
    _failed[key].append(time.time())


def sign(message: str, agent_id: str) -> str:
    from config.settings import get_settings as _gs
    key = f"{_gs().app_secret_key}:{agent_id}".encode()
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()


def verify(message: str, signature: str, agent_id: str) -> bool:
    return hmac.compare_digest(sign(message, agent_id), signature)
