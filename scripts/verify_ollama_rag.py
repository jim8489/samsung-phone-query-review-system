from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services.chat import ChatService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify an actual Ollama-backed, database-grounded RAG response.")
    parser.add_argument(
        "--query",
        default="What are the rear camera specifications of the Samsung Galaxy S23?",
        help="Question to send through the application's real RAG pipeline.",
    )
    args = parser.parse_args()

    if settings.llm_provider == "none":
        print("[FAILED] LLM_PROVIDER=none. Set LLM_PROVIDER=ollama in .env and restart this command.")
        raise SystemExit(2)

    try:
        response = httpx.get(settings.ollama_base_url.rstrip("/") + "/api/tags", timeout=5.0)
        response.raise_for_status()
        payload = response.json()
        model_names = [item.get("name", "") for item in payload.get("models", []) if isinstance(item, dict)]
    except Exception as exc:
        print(f"[FAILED] Ollama is not reachable at {settings.ollama_base_url}: {exc}")
        print("Start Ollama and run: ollama pull " + settings.ollama_model)
        raise SystemExit(2) from exc

    available = any(
        name == settings.ollama_model or name.split(":", 1)[0] == settings.ollama_model.split(":", 1)[0]
        for name in model_names
    )
    if not available:
        print(f"[FAILED] Model {settings.ollama_model!r} is not installed. Run: ollama pull {settings.ollama_model}")
        print("Installed models:", ", ".join(model_names) or "none")
        raise SystemExit(2)

    with SessionLocal() as db:
        result = asyncio.run(ChatService(db).ask(args.query))

    print("RAG query:", args.query)
    print("Generation mode:", result["mode"])
    print("Relevant phones:", ", ".join(result["relevant_phones"]) or "none")
    print("Sources:")
    for source in result["sources"]:
        print(f"- {source.get('title')}: {source.get('url') or source.get('source')}")
    print("\nAnswer:\n")
    print(result["answer"])

    if result["mode"] != "ollama_rag":
        print("\n[FAILED] The answer used the deterministic fallback, not Ollama generation.")
        raise SystemExit(1)
    print("\n[PASS] The chatbot generated a response through the configured Ollama model using retrieved database evidence.")


if __name__ == "__main__":
    main()
