"""Guardrail 4 – Data Privacy · consent · anonymization · retention · access control"""
import re, hashlib, logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from config.settings import get_settings

log = logging.getLogger("guard.privacy")
cfg = get_settings()

_consent: Dict[str, Dict] = {}
_pseudonyms: Dict[str, str] = {}
_created: Dict[str, datetime] = {}

PII_FIELDS = {"name","email","phone","address","ssn","dob","credit_card"}
PII_RE = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"),
}


def record_consent(user_id: str, consented: bool, purposes: List[str], ip: str = "") -> Dict:
    rec = {"user_id": user_id, "consented": consented, "purposes": purposes,
           "timestamp": datetime.now(timezone.utc).isoformat(), "ip": ip}
    _consent[user_id] = rec
    log.info(f"Consent {'granted' if consented else 'denied'} user={user_id}")
    return rec


def check_consent(user_id: str, purpose: str) -> Tuple[bool, str]:
    if not cfg.consent_required:
        return True, "Consent not required"
    r = _consent.get(user_id)
    if not r:
        return False, "No consent record found. POST /api/v1/consent first."
    if not r["consented"]:
        return False, "User has not consented."
    if purpose not in r["purposes"]:
        return False, f"Consent not given for purpose '{purpose}'."
    return True, "Consent verified."


def withdraw_consent(user_id: str) -> bool:
    if user_id in _consent:
        _consent[user_id]["consented"] = False
        return True
    return False


def anonymize(data: Dict) -> Dict:
    if not cfg.anonymization:
        return data
    out = {}
    for k, v in data.items():
        if k.lower() in PII_FIELDS:
            h = hashlib.sha256(str(v).encode()).hexdigest()[:8]
            out[k] = f"[ANON_{k.upper()}_{h}]"
        elif isinstance(v, str):
            val = v
            for name, pat in PII_RE.items():
                val = pat.sub(f"[REDACTED_{name.upper()}]", val)
            out[k] = val
        else:
            out[k] = v
    return out


def pseudonymize(user_id: str) -> str:
    if user_id not in _pseudonyms:
        h = hashlib.sha256((user_id + cfg.encryption_key).encode()).hexdigest()[:16]
        _pseudonyms[user_id] = f"pseudo_{h}"
    return _pseudonyms[user_id]


def check_access(requestor: str, owner: str, data_type: str) -> Tuple[bool, str]:
    if requestor == owner:
        return True, "Owner access granted."
    if requestor.startswith("admin_"):
        return True, "Admin access granted."
    log.warning(f"Unauthorized access attempt: {requestor} -> {owner} ({data_type})")
    return False, f"Access denied: '{requestor}' cannot access data of '{owner}'."


def register_data(data_id: str):
    _created[data_id] = datetime.now(timezone.utc)


def is_expired(data_id: str) -> bool:
    c = _created.get(data_id)
    if not c:
        return False
    return datetime.now(timezone.utc) > c + timedelta(days=cfg.data_retention_days)
