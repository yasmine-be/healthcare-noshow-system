import json
import os
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv
from fastapi import HTTPException
from pydantic import ValidationError

import schemas

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
ACTION_LABELS = {
    "send_reminder": "Envoyer un rappel neutre au patient.",
    "request_confirmation": "Demander au patient de confirmer ou déplacer le rendez-vous.",
    "staff_call": "Proposer à un membre du personnel de vérifier les disponibilités.",
    "no_extra_action": "Aucune action supplémentaire n'est suggérée.",
}
DISCLAIMER = (
    "Suggestion automatique à valider par le personnel; elle ne constitue pas "
    "un avis médical ni une décision."
)


def _validate_local_endpoint() -> str:
    try:
        parsed = urlsplit(OLLAMA_BASE_URL)
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="GenAI local endpoint configuration is invalid",
        ) from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(
            status_code=503,
            detail="GenAI is restricted to a local Ollama service",
        )
    return f"{OLLAMA_BASE_URL}/api/chat"


def generate_advice(request: schemas.AgentAdviceRequest) -> schemas.AgentAdvice:
    endpoint = _validate_local_endpoint()
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a staff workflow assistant for appointment attendance. "
                    "Reply only in French as JSON with a short summary and an actions "
                    "array containing only these exact codes: send_reminder, "
                    "request_confirmation, staff_call, no_extra_action. Explain "
                    "uncertainty; do not diagnose, give medical advice, invent facts, "
                    "recommend punishment, or make decisions. A human must approve "
                    "every action. Use only the supplied numeric features. Never ask "
                    "for patient identity or additional personal or health information."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    request.model_dump(),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
    }

    try:
        response = requests.post(
            endpoint,
            json=payload,
            timeout=90,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail="Local GenAI service is unavailable or timed out",
        ) from exc

    if not 200 <= response.status_code < 300:
        raise HTTPException(
            status_code=502,
            detail=f"Local GenAI service returned HTTP {response.status_code}",
        )

    try:
        content = response.json()["message"]["content"]
        draft = schemas.AgentAdviceDraft.model_validate_json(content)
    except (ValueError, KeyError, TypeError, ValidationError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Local GenAI service returned an invalid advice response",
        ) from exc
    return schemas.AgentAdvice(
        summary=draft.summary,
        actions=[ACTION_LABELS[action] for action in draft.actions],
        disclaimer=DISCLAIMER,
    )
