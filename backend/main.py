"""
PyChat AI - Milestone 3

FastAPI web server exposing:

    GET  /           - basic info about the app
    GET  /health     - liveness check + Ollama status
    POST /api/chat   - send a message, get a reply

Run from the project root with:

    uvicorn backend.main:app --reload

Interactive docs are then available at http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from backend import ai, config
from backend.ai import AIServiceError


# ---------------------------------------------------------------------------
# Pydantic models — request and response schemas
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """One turn in a conversation."""

    role: str
    content: str = Field(
        ...,
        min_length=1,
        max_length=config.MAX_HISTORY_ITEM_LENGTH,
        description="The text of the message.",
    )

    @field_validator("role")
    @classmethod
    def _role_must_be_known(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")
        return normalized


class ChatRequest(BaseModel):
    """Body of POST /api/chat."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=config.MAX_MESSAGE_LENGTH,
        description="The user's new message.",
    )
    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=config.MAX_HISTORY_MESSAGES,
        description="Recent conversation history (oldest first).",
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
# Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """Landing endpoint — useful for a quick 'is it up?' check."""
    return {
        "name": config.BOT_NAME,
        "version": config.BOT_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


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

    The server prepends the system prompt and trusts the client's history
    ordering. History length is capped by ChatRequest itself.
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
        # 503 = "the server is fine, but a dependency it needs is not."
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return ChatResponse(reply=reply)