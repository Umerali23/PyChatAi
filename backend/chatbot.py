"""
PyChat AI - Milestone 2

Terminal chatbot that talks to a real local LLM through Ollama.

Run from the project root with:
    python -m backend.chatbot
"""

from backend import ai, config
from backend.ai import AIServiceError


def print_banner() -> None:
    print("=" * 55)
    print(f"  {config.BOT_NAME}  v{config.BOT_VERSION}")
    print(f"  Model: {config.DEFAULT_MODEL}")
    print("  Type /help for commands, 'exit' to quit.")
    print("=" * 55)
    print()


def print_help() -> None:
    print(
        "Commands:\n"
        "  /help    show this message\n"
        "  /reset   clear the conversation history\n"
        "  /about   show bot and model info\n"
        "  /models  list installed Ollama models\n"
        "  exit     quit\n"
    )


def print_about() -> None:
    print(
        f"{config.BOT_NAME} v{config.BOT_VERSION}\n"
        f"Backend: Ollama at {config.OLLAMA_URL}\n"
        f"Model:   {config.DEFAULT_MODEL}\n"
    )


def print_models() -> None:
    try:
        models = ai.list_models()
    except AIServiceError as exc:
        print(f"[error] {exc}\n")
        return

    if not models:
        print("No models installed. Try: ollama pull qwen2.5:1.5b\n")
        return

    print("Installed models:")
    for name in models:
        print(f"  - {name}")
    print()


def build_messages(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Prepend the system prompt and trim history so we never send more than
    config.MAX_HISTORY_MESSAGES past messages.
    """
    recent = history[-config.MAX_HISTORY_MESSAGES:]
    return [{"role": "system", "content": config.SYSTEM_PROMPT}, *recent]


def chat_loop() -> None:
    print_banner()

    if not ai.is_ollama_running():
        print(
            "[warning] Ollama does not appear to be running.\n"
            "          On Windows, look for the Ollama icon in your system tray.\n"
            "          If it is not there, open another terminal and run:\n"
            "              ollama serve\n"
        )

    history: list[dict[str, str]] = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nPyChat AI: Goodbye!")
            break

        if not user_input:
            print("PyChat AI: It looks like you didn't type anything.\n")
            continue

        lowered = user_input.lower()

        if lowered in config.EXIT_COMMANDS:
            print("PyChat AI: Goodbye! See you next time.")
            break

        if lowered == "/help":
            print_help()
            continue

        if lowered == "/reset":
            history.clear()
            print("PyChat AI: Conversation history cleared.\n")
            continue

        if lowered == "/about":
            print_about()
            continue

        if lowered == "/models":
            print_models()
            continue

        # Normal message: record it, then ask the model.
        history.append({"role": "user", "content": user_input})

        try:
            reply = ai.chat(build_messages(history))
        except AIServiceError as exc:
            print(f"PyChat AI [error]: {exc}\n")
            # Remove the failed user message so history stays consistent
            # with what the model actually saw.
            history.pop()
            continue

        history.append({"role": "assistant", "content": reply})
        print(f"PyChat AI: {reply}\n")


if __name__ == "__main__":
    chat_loop()