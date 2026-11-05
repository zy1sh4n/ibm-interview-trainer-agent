"""Guardrail 7 – Human-in-the-Loop · approval gates · escalation · timeout"""
import uuid, logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from config.settings import get_settings

log = logging.getLogger("guard.hitl")
cfg = get_settings()

ALWAYS_NEED_APPROVAL = {"delete_user_data", "send_email", "financial_transaction", "modify_config"}
_store: Dict[str, Dict] = {}


def request_approval(action: str, description: str, payload: Dict,
                     requester: str = "agent", risk: str = "medium") -> Dict:
    req_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    status = "auto_approved"

    needs = (action in ALWAYS_NEED_APPROVAL) or (risk in ("high", "critical")) or cfg.hitl_enabled
    if needs and cfg.app_env != "development":
        status = "pending"

    req = {
        "request_id": req_id, "action": action, "description": description,
        "payload": payload, "requester": requester, "risk": risk,
        "status": status,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=cfg.hitl_timeout)).isoformat(),
    }
    if status == "pending":
        _store[req_id] = req
        log.info(f"HITL approval requested: {req_id} action={action} risk={risk}")
    return req


def approve(req_id: str, reviewer: str, notes: str = "") -> bool:
    r = _store.get(req_id)
    if not r:
        return False
    r.update({"status": "approved", "reviewer": reviewer, "notes": notes,
               "reviewed_at": datetime.now(timezone.utc).isoformat()})
    log.info(f"HITL APPROVED: {req_id} by {reviewer}")
    return True


def reject(req_id: str, reviewer: str, reason: str) -> bool:
    r = _store.get(req_id)
    if not r:
        return False
    r.update({"status": "rejected", "reviewer": reviewer, "reason": reason,
               "reviewed_at": datetime.now(timezone.utc).isoformat()})
    log.info(f"HITL REJECTED: {req_id} by {reviewer}")
    return True


def is_approved(req_id: str) -> bool:
    r = _store.get(req_id)
    if not r:
        return False
    if r["status"] == "pending":
        expires = datetime.fromisoformat(r["expires_at"])
        if datetime.now(timezone.utc) > expires:
            r["status"] = "timed_out"
            log.warning(f"HITL timed out: {req_id} — escalating to {cfg.hitl_escalation_email}")
            return False
    return r["status"] in ("approved", "auto_approved")


def pending() -> List[Dict]:
    return [r for r in _store.values() if r["status"] == "pending"]
