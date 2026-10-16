"""Bounded Gemini retries, optional explicit fallback, and redacted failure categories."""
import logging
import os
import random
import time

import httpx

LOGGER = logging.getLogger(__name__)
BUSY_MESSAGE = "The AI provider is busy or temporarily unavailable. Please try again shortly."


class ProviderUnavailable(RuntimeError):
    """A transient provider failure persisted after the bounded attempts."""


def transient(exc):
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    return code in (429, 500, 502, 503, 504) or isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))


class ResilientModel:
    def __init__(self, primary, fallback=None):
        self.primary, self.fallback = primary, fallback

    def invoke(self, prompt):
        # Two total attempts, including fallback; SDK retries are disabled below.
        for attempt, model in enumerate((self.primary, self.fallback or self.primary), start=1):
            try:
                return model.invoke(prompt)
            except Exception as exc:
                if not transient(exc):
                    raise
                # Never log raw exceptions: provider/driver messages can contain secrets.
                LOGGER.warning("provider_transient_failure attempt=%s category=%s", attempt, type(exc).__name__)
                if attempt == 2:
                    raise ProviderUnavailable(BUSY_MESSAGE) from None
                time.sleep(1 + random.random())


def make_model(schema):
    from langchain_google_genai import ChatGoogleGenerativeAI

    primary = os.environ.get("GEMINI_MODEL")
    if not primary:
        raise RuntimeError("GEMINI_MODEL is not set")

    def build(name):
        # In this pinned integration max_retries is SDK total attempts, not extra retries.
        return ChatGoogleGenerativeAI(model=name, temperature=0, api_key=os.environ["GEMINI_API_KEY"],
                                      max_retries=1, timeout=25, max_output_tokens=4096).with_structured_output(schema)

    fallback = os.environ.get("GEMINI_FALLBACK_MODEL", "").strip()
    return ResilientModel(build(primary), build(fallback) if fallback and fallback != primary else None)
