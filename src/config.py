"""Central configuration and the single most important safety guard in this repo:
we are only ever allowed to call the assessment test number.
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# HARD GUARD: the assessment says to call ONLY this number, and explicitly NOT
# the number shown on the pgai.us/athena confirmation screen. We hardcode it so
# a bad .env value or typo can never dial somewhere else.
# ---------------------------------------------------------------------------
TARGET_NUMBER = "+18054398008"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "8000"))

REALTIME_MODEL = os.getenv("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
REALTIME_VOICE = os.getenv("REALTIME_VOICE", "alloy")

# OpenAI Realtime WebSocket endpoint.
REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"


def assert_target_allowed(number: str) -> None:
    """Raise unless `number` is exactly the assessment test line."""
    if number != TARGET_NUMBER:
        raise ValueError(
            f"Refusing to dial {number!r}. This bot may only call the assessment "
            f"test number {TARGET_NUMBER}."
        )


def validate_runtime_env() -> list[str]:
    """Return a list of human-readable problems with the current environment."""
    problems = []
    if not OPENAI_API_KEY:
        problems.append("OPENAI_API_KEY is not set")
    if not TWILIO_ACCOUNT_SID:
        problems.append("TWILIO_ACCOUNT_SID is not set")
    if not TWILIO_AUTH_TOKEN:
        problems.append("TWILIO_AUTH_TOKEN is not set")
    if not TWILIO_FROM_NUMBER:
        problems.append("TWILIO_FROM_NUMBER is not set")
    if not PUBLIC_URL:
        problems.append("PUBLIC_URL is not set (run ngrok and paste the https URL)")
    return problems
