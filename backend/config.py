"""
Centralized configuration for PyChat AI.

Everything that might change between machines, models, or environments lives
here. This means we never hardcode the model name, the Ollama URL, or the
system prompt in more than one place.
"""

# --- Application ----------------------------------------------------------

BOT_NAME: str = "PyChat AI"
BOT_VERSION: str = "0.2.0"

EXIT_COMMANDS: set[str] = {"exit", "quit", "q"}

# --- Ollama ---------------------------------------------------------------

OLLAMA_URL: str = "http://127.0.0.1:11434"
OLLAMA_CHAT_ENDPOINT: str = f"{OLLAMA_URL}/api/chat"
OLLAMA_TAGS_ENDPOINT: str = f"{OLLAMA_URL}/api/tags"

# For a GTX 1060 3GB, a 1.5B-parameter model fits comfortably in VRAM.
# Larger models spill over to CPU (slow) or fail to load.
DEFAULT_MODEL: str = "qwen2.5:1.5b"

# Generous timeout: the first request to a model can take a while to load.
REQUEST_TIMEOUT: int = 120
HEALTH_CHECK_TIMEOUT: int = 5

# --- Conversation ---------------------------------------------------------

# How many past messages to send with each request. Older messages are
# dropped. This keeps requests small and prevents the model's context
# window from overflowing during long chats.
MAX_HISTORY_MESSAGES: int = 20

# The system prompt tells the model how to behave. It is prepended to every
# request and is never shown to the user.
SYSTEM_PROMPT: str = (
    "You are PyChat AI, a helpful, friendly, and concise assistant running "
    "locally on the user's computer. Follow these rules:\n"
    "- Be helpful, accurate, and to the point.\n"
    "- Use plain, clear language.\n"
    "- If you do not know something, say so honestly instead of guessing.\n"
    "- Do not invent facts, sources, or capabilities you do not have.\n"
    "- Keep replies short unless the user asks for detail."
)