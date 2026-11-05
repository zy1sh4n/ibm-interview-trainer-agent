"""
Guardrail 1 – Input Guardrails
Prompt injection · PII · malicious input · content filtering · length
"""
import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from config.settings import get_settings

log = logging.getLogger("guard.input")
cfg = get_settings()

INJECTION_RE = [re.compile(p, re.I | re.S) for p in [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?instructions",
    r"forget\s+(all\s+)?previous",
    r"\bDAN\b", r"do\s+anything\s+now",
    r"bypass\s+(all\s+)?restrictions",
    r"override\s+(all\s+)?(?:safety|guidelines|rules)",
    r"print\s+your\s+(system\s+)?prompt",
    r"reveal\s+your\s+(system\s+)?instructions",
    r"you\s+are\s+now\s+(a\s+)?(?:DAN|evil|unrestricted)",
    r"pretend\s+(you|that)\s+(are|you're)\s+",
    r"<\|.*?\|>",
]]
MALICIOUS_RE = [re.compile(p, re.I) for p in [
    r";\s*DROP\s+TABLE", r";\s*DELETE\s+FROM",
    r"UNION\s+SELECT", r"<script[^>]*>",
    r"javascript:", r"__import__\s*\(",
    r"os\.system\s*\(", r"subprocess\.",
]]
PII_RE = {
    "email":   re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone":   re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"),
    "ssn":     re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}
BAD_WORDS = ["kill", "murder", "bomb", "terrorist", "hack into", "steal credentials"]


@dataclass
class InputResult:
    is_valid: bool
    clean: str
    violations: List[str] = field(default_factory=list)
    pii_found: List[str] = field(default_factory=list)
    risk: float = 0.0


def validate(text: str, user_id: str = "anon") -> InputResult:
    v, pii, risk = [], [], 0.0

    # 1. Length
    if len(text.strip()) < cfg.input_min_length:
        v.append(f"Input too short (min {cfg.input_min_length} chars)")
        risk += 0.3
    if len(text) > cfg.input_max_length:
        v.append(f"Input too long (max {cfg.input_max_length} chars)")
        risk += 0.2

    # 2. Prompt injection
    if cfg.prompt_injection_detection:
        for r in INJECTION_RE:
            if r.search(text):
                v.append("Prompt injection detected")
                risk = max(risk, 0.9)
                break

    # 3. Malicious content
    for r in MALICIOUS_RE:
        if r.search(text):
            v.append("Malicious content detected")
            risk = max(risk, 0.8)
            break

    # 4. PII
    if cfg.pii_detection:
        for name, pattern in PII_RE.items():
            if pattern.search(text):
                pii.append(name)

    # 5. Inappropriate
    if cfg.content_filter:
        lower = text.lower()
        if any(w in lower for w in BAD_WORDS):
            v.append("Inappropriate content detected")
            risk = max(risk, 0.7)

    # Sanitise
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    for name, pattern in PII_RE.items():
        clean = pattern.sub(f"[REDACTED_{name.upper()}]", clean)

    is_valid = len(v) == 0
    if not is_valid:
        log.warning(f"Input blocked user={user_id} violations={v}")
    return InputResult(is_valid=is_valid, clean=clean, violations=v, pii_found=pii, risk=round(min(risk,1.0),2))
