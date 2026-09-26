"""
PyChat AI - Milestone 4

FastAPI web server exposing:

    GET  /           - the frontend (index.html)
    GET  /health     - liveness check + Ollama status
    GET  /api/info   - small JSON info about the API
    POST /api/chat   - send a message, get a reply

The frontend folder is served from the same server, so no CORS issues
and only one process to run.

Run from the project root with:

    uvicorn backend.main:app --reload

Then open http://127.0.0.1:8000/ in your browser.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from backend import ai, config
from backend.ai import AIServiceError


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str = Field(
        ...,
        min_length=1,
        max_length=config.MAX_HISTORY_ITEM_LENGTH,
    )

    @field_validator("role")
    @classmethod
    def _role_must_be_known(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")
        return normalized


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=config.MAX_MESSAGE_LENGTH,
    )
    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=config.MAX_HISTORY_MESSAGES,
    )

    @field_validator("message")
    @classmethod
    def _message_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be empty or whitespace")
        return stripped


class ChatResponse(BaseModel):
    reply: str


class HealthResponse(BaseModel):
    status: str
    ollama_running: bool
    model: str
    version: str


class InfoResponse(BaseModel):
    name: str
    version: str
    docs: str
    health: str
    chat: str


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title=config.BOT_NAME,
    version=config.BOT_VERSION,
    description="Local AI chatbot backend powered by Ollama.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# API routes — registered BEFORE the static mount so they take priority.
# ---------------------------------------------------------------------------

@app.get("/api/info", response_model=InfoResponse, tags=["meta"])
def info() -> InfoResponse:
    """Small JSON info endpoint about the API itself."""
    return InfoResponse(
        name=config.BOT_NAME,
        version=config.BOT_VERSION,
        docs="/docs",
        health="/health",
        chat="/api/chat",
    )


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Liveness check plus a quick look at Ollama."""
    return HealthResponse(
        status="ok",
        ollama_running=ai.is_ollama_running(),
        model=config.DEFAULT_MODEL,
        version=config.BOT_VERSION,
    )


@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    Accept a user message plus optional history, ask Ollama, return the reply.
    The server prepends the system prompt; history length is capped by
    ChatRequest itself.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": config.SYSTEM_PROMPT}
    ]
    messages.extend(
        {"role": item.role, "content": item.content} for item in request.history
    )
    messages.append({"role": "user", "content": request.message})

    try:
        reply = ai.chat(messages)
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return ChatResponse(reply=reply)


# ---------------------------------------------------------------------------
# Static frontend — mounted LAST so API routes above take precedence.
# ---------------------------------------------------------------------------

if FRONTEND_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )
else:
    warnings.warn(
        f"Frontend directory not found at {FRONTEND_DIR}. "
        "The web UI will not be served."
    )