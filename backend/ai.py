"""
AI service for PyChat AI.

This is the ONLY module in the project that knows how to talk to Ollama.
Everything else calls functions here. That way, if we ever swap Ollama for
another provider, only this file has to change.
"""

from __future__ import annotations

import requests

from backend import config


class AIServiceError(Exception):
    """A friendly, user-facing error raised by the AI service."""


def is_ollama_running() -> bool:
    """Return True if the Ollama HTTP server responds on its tags endpoint."""
    try:
        response = requests.get(
            config.OLLAMA_TAGS_ENDPOINT,
            timeout=config.HEALTH_CHECK_TIMEOUT,
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def list_models() -> list[str]:
    """Return the names of models currently installed in Ollama."""
    try:
        response = requests.get(
            config.OLLAMA_TAGS_ENDPOINT,
            timeout=config.HEALTH_CHECK_TIMEOUT,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise AIServiceError(
            "Could not connect to Ollama. Is it running? On Windows, check "
            "for the Ollama icon in the system tray, or run 'ollama serve' "
            "in a separate terminal."
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise AIServiceError("Ollama did not respond in time.") from exc
    except requests.exceptions.RequestException as exc:
        raise AIServiceError(f"Failed to reach Ollama: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise AIServiceError("Ollama returned an invalid JSON response.") from exc

    return [
        model.get("name", "")
        for model in data.get("models", [])
        if model.get("name")
    ]


def chat(
    messages: list[dict[str, str]],
    model: str | None = None,
) -> str:
    """
    Send a conversation to Ollama and return the assistant's reply text.

    `messages` must be a list of dicts shaped like:
        {"role": "system" | "user" | "assistant", "content": "..."}
    """
    chosen_model = model or config.DEFAULT_MODEL

    payload = {
        "model": chosen_model,
        "messages": messages,
        "stream": False,  # we get the whole reply in one response
    }

    try:
        response = requests.post(
            config.OLLAMA_CHAT_ENDPOINT,
            json=payload,
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.exceptions.ConnectionError as exc:
        raise AIServiceError(
            "Could not connect to Ollama. Make sure Ollama is running. "
            "On Windows, look for the Ollama icon in the system tray."
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise AIServiceError(
            f"Ollama did not respond within {config.REQUEST_TIMEOUT} seconds. "
            "The model may be loading for the first time. Try again."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise AIServiceError(f"Network error talking to Ollama: {exc}") from exc

    if response.status_code == 404:
        raise AIServiceError(
            f"Model '{chosen_model}' is not installed. "
            f"Run: ollama pull {chosen_model}"
        )

    if not response.ok:
        detail = _extract_error_message(response)
        raise AIServiceError(
            f"Ollama returned HTTP {response.status_code}: {detail}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise AIServiceError("Ollama returned an invalid JSON response.") from exc

    reply = data.get("message", {}).get("content")
    if not isinstance(reply, str) or not reply.strip():
        # Something unexpected came back. Show a short, safe preview.
        preview = str(data)[:300]
        raise AIServiceError(
            f"Ollama returned an empty or malformed response. Raw: {preview}"
        )

    return reply.strip()


def _extract_error_message(response: requests.Response) -> str:
    """Ollama usually returns an {'error': '...'} JSON body on failures."""
    try:
        data = response.json()
        if isinstance(data, dict) and "error" in data:
            return str(data["error"])
    except ValueError:
        pass
    return response.text.strip() or "(no message)"