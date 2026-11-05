"""
Guardrail 2 – Output Guardrails
Hallucination · toxicity · sensitive info · format · length
"""
import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from config.settings import get_settings

log = logging.getLogger("guard.output")
cfg = get_settings()

TOXIC_RE = [re.compile(p, re.I) for p in [
    r"\b(kill|murder|suicide|bomb|terrorist)\b",
    r"\b(hack\s+into|steal\s+credentials)\b",
    r"this\s+(candidate|applicant)\s+(is\s+)?(incompetent|stupid|worthless)",
]]
SENSITIVE_RE = [re.compile(p, re.I) for p in [
    r"password\s*(is|=|:)\s*\S+",
    r"IBM_WATSONX_API_KEY\s*=",
    r"secret[_\s]key\s*(is|=|:)\s*\S+",
]]
HALLUCINATION_PHRASES = [
    "i made up", "this is speculation", "i cannot verify",
    "based on my training data which may be outdated",
    "i don't have real-time",
]


@dataclass
class OutputResult:
    is_valid: bool
    text: str
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    hallucination_risk: float = 0.0
    toxicity_score: float = 0.0


def validate(text: str, context_docs: Optional[List[str]] = None) -> OutputResult:
    v, w = [], []
    filtered = text

    # 1. Empty
    if not text.strip():
        return OutputResult(is_valid=False, text=text, violations=["Empty response"])

    # 2. Length
    if len(text) > cfg.output_max_length:
        filtered = text[:cfg.output_max_length]
        w.append("Response truncated to max length")

    # 3. Toxicity
    if cfg.toxicity_filter:
        hits = sum(1 for r in TOXIC_RE if r.search(filtered))
        score = round(min(hits * 0.25, 1.0), 2)
        if score > 0:
            v.append("Toxic content detected")
        else:
            score = 0.0
    else:
        score = 0.0

    # 4. Sensitive info
    for r in SENSITIVE_RE:
        if r.search(filtered):
            filtered = r.sub("[REDACTED]", filtered)
            v.append("Sensitive information redacted")
            break

    # 5. Hallucination heuristic
    lower = filtered.lower()
    h_hits = sum(1 for p in HALLUCINATION_PHRASES if p in lower)
    hall_risk = round(min(h_hits * 0.15, 0.9), 2)
    if context_docs:
        import re as _re
        resp_words = set(_re.findall(r"\b\w{5,}\b", lower))
        ctx_words = set()
        for d in context_docs:
            ctx_words.update(_re.findall(r"\b\w{5,}\b", d.lower()))
        if resp_words:
            overlap = len(resp_words & ctx_words) / len(resp_words)
            hall_risk = round(max(hall_risk, 0.8 - overlap), 2)
    if hall_risk > 0.6:
        w.append(f"Potential hallucination (risk={hall_risk})")

    is_valid = len(v) == 0
    return OutputResult(is_valid=is_valid, text=filtered, violations=v, warnings=w,
                        hallucination_risk=hall_risk, toxicity_score=score)
