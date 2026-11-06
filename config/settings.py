"""
IBM Interview Trainer Agent – Settings
Reads from: .env file (local) OR Streamlit st.secrets (Streamlit Cloud).
"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _st_secrets() -> dict:
    """Pull IBM credentials from st.secrets when running on Streamlit Cloud."""
    try:
        import streamlit as st
        sec = dict(st.secrets)
        # Flatten nested [ibm] section if present
        if "ibm" in sec and isinstance(sec["ibm"], dict):
            sec.update({f"ibm_{k}": v for k, v in sec["ibm"].items()})
        return sec
    except Exception:
        return {}


class Settings(BaseSettings):
    # App
    app_name: str = Field(default="IBM Interview Trainer Agent")
    app_version: str = Field(default="1.0.0")
    app_env: str = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    app_debug: bool = Field(default=False)
    app_secret_key: str = Field(default="change-me-in-production-32-chars!!")
    app_log_level: str = Field(default="INFO")

    # IBM WatsonX / Granite (MANDATORY for live mode)
    ibm_watsonx_api_key: str = Field(default="")
    ibm_watsonx_url: str = Field(default="https://us-south.ml.cloud.ibm.com")
    ibm_watsonx_project_id: str = Field(default="")
    ibm_granite_model_id: str = Field(default="ibm/granite-3-8b-instruct")
    ibm_granite_embedding_model: str = Field(default="ibm/slate-125m-english-rtrvr")

    # RAG
    rag_top_k: int = Field(default=4)
    rag_similarity_threshold: float = Field(default=0.3)

    # Guardrails – Input
    input_max_length: int = Field(default=5000)
    input_min_length: int = Field(default=3)
    pii_detection: bool = Field(default=True)
    prompt_injection_detection: bool = Field(default=True)
    content_filter: bool = Field(default=True)

    # Guardrails – Output
    hallucination_check: bool = Field(default=True)
    toxicity_filter: bool = Field(default=True)
    output_max_length: int = Field(default=8000)

    # Guardrails – Security
    jailbreak_detection: bool = Field(default=True)
    max_failed_attempts: int = Field(default=5)
    lockout_minutes: int = Field(default=15)

    # Guardrails – Operational
    execution_timeout: int = Field(default=120)
    max_retries: int = Field(default=3)
    rate_limit_rpm: int = Field(default=30)
    max_tokens_per_request: int = Field(default=2048)
    max_tokens_per_session: int = Field(default=20000)
    monthly_token_budget: int = Field(default=1_000_000)
    max_iterations: int = Field(default=10)

    # Guardrails – HITL
    hitl_enabled: bool = Field(default=True)
    hitl_escalation_email: str = Field(default="admin@company.com")
    hitl_timeout: int = Field(default=300)

    # Multi-Agent
    max_agents: int = Field(default=6)
    max_handoffs: int = Field(default=10)

    # Privacy
    data_retention_days: int = Field(default=90)
    anonymization: bool = Field(default=True)
    consent_required: bool = Field(default=True)
    encryption_key: str = Field(default="change-this-32-byte-key-in-prod!!")

    # Ethical
    bias_detection: bool = Field(default=True)
    audit_trail: bool = Field(default=True)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    # On Streamlit Cloud, .env doesn't exist — override from st.secrets
    if not s.ibm_watsonx_api_key:
        sec = _st_secrets()
        if sec.get("ibm_watsonx_api_key"):
            # Re-create settings with the secrets injected as env overrides
            import os
            os.environ.setdefault("IBM_WATSONX_API_KEY",    sec.get("ibm_watsonx_api_key", ""))
            os.environ.setdefault("IBM_WATSONX_PROJECT_ID", sec.get("ibm_watsonx_project_id", ""))
            os.environ.setdefault("IBM_WATSONX_URL",        sec.get("ibm_watsonx_url", s.ibm_watsonx_url))
            get_settings.cache_clear()
            return Settings()
    return s
