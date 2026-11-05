"""
IBM Granite Client
Calls IBM WatsonX AI (ibm-watsonx-ai SDK).
Falls back to a descriptive mock when credentials are not configured.
"""
import time
import logging
from typing import Any, Dict, List, Optional
from config.settings import get_settings

log = logging.getLogger("granite")
cfg = get_settings()


class GraniteClient:
    """Thin wrapper around ibm-watsonx-ai ModelInference."""

    def __init__(self):
        self._model = None
        self._tokens_used = 0
        self._init()

    def _init(self):
        if not cfg.ibm_watsonx_api_key or not cfg.ibm_watsonx_project_id:
            log.warning("IBM credentials not set — running in MOCK mode.")
            return
        try:
            from ibm_watsonx_ai import APIClient, Credentials
            from ibm_watsonx_ai.foundation_models import ModelInference
            creds = Credentials(url=cfg.ibm_watsonx_url, api_key=cfg.ibm_watsonx_api_key)
            client = APIClient(creds)
            self._model = ModelInference(
                model_id=cfg.ibm_granite_model_id,
                api_client=client,
                project_id=cfg.ibm_watsonx_project_id,
            )
            log.info(f"IBM Granite connected: {cfg.ibm_granite_model_id}")
        except Exception as e:
            log.error(f"IBM WatsonX init failed: {e}")

    def generate(self, prompt: str, max_tokens: int = 800) -> Dict[str, Any]:
        """Generate text. Returns dict with 'text', 'tokens', 'model', 'mock'."""
        t0 = time.time()
        max_t = min(max_tokens, cfg.max_tokens_per_request)

        if self._model is None:
            return self._mock(prompt)

        for attempt in range(1, cfg.max_retries + 1):
            try:
                text = self._model.generate_text(
                    prompt=prompt,
                    params={"max_new_tokens": max_t, "temperature": 0.7, "decoding_method": "sample"},
                )
                tokens = (len(prompt) + len(text)) // 4
                self._tokens_used += tokens
                return {
                    "text": text, "tokens": tokens,
                    "model": cfg.ibm_granite_model_id,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "mock": False,
                }
            except Exception as e:
                log.warning(f"Attempt {attempt} failed: {e}")
                time.sleep(2 ** attempt)

        return {"text": "", "tokens": 0, "model": "", "latency_ms": 0, "mock": False, "error": "retries exhausted"}

    @staticmethod
    def _mock(prompt: str) -> Dict[str, Any]:
        sample = (
            "IBM Granite (mock mode): Configure IBM_WATSONX_API_KEY and "
            "IBM_WATSONX_PROJECT_ID in your .env file to use the real model.\n\n"
            "Example interview question: 'Tell me about a challenging project you led and "
            "what you learned from it.' Use the STAR method in your answer."
        )
        return {"text": sample, "tokens": len(prompt) // 4, "model": "mock", "latency_ms": 5, "mock": True}

    @property
    def total_tokens(self) -> int:
        return self._tokens_used
