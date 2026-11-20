from __future__ import annotations

import importlib.util

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Phone
from app.schemas import HealthResponse

router = APIRouter(tags=["System"])


@router.get("/health", response_model=HealthResponse, summary="Service health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    count = db.scalar(select(func.count()).select_from(Phone)) or 0
    return HealthResponse(
        status=f"ok ({count} phones loaded)",
        version=settings.app_version,
        database="connected",
        llm_provider=settings.llm_provider,
    )


@router.get("/llm", summary="Check Ollama reachability and configured model availability")
async def llm_status():
    if settings.llm_provider == "none":
        return {
            "provider": "none",
            "reachable": False,
            "model": settings.ollama_model,
            "model_available": False,
            "detail": "LLM calls are disabled by LLM_PROVIDER=none.",
        }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(settings.ollama_base_url.rstrip("/") + "/api/tags")
            response.raise_for_status()
            payload = response.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        names = [item.get("name", "") for item in models if isinstance(item, dict)]
        configured = settings.ollama_model
        available = any(name == configured or name.split(":", 1)[0] == configured.split(":", 1)[0] for name in names)
        return {
            "provider": "ollama",
            "reachable": True,
            "model": configured,
            "model_available": available,
            "installed_models": names,
            "detail": "Configured model is installed." if available else f"Run: ollama pull {configured}",
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "provider": "ollama",
            "reachable": False,
            "model": settings.ollama_model,
            "model_available": False,
            "detail": f"Cannot reach Ollama at {settings.ollama_base_url}: {exc}",
        }


@router.get("/agents", summary="Describe the configured multi-agent pipeline")
def agent_status():
    langchain_installed = importlib.util.find_spec("langchain") is not None
    langchain_ollama_installed = importlib.util.find_spec("langchain_ollama") is not None
    return {
        "orchestrator": "LangChainMultiAgentWorkflow" if settings.agent_framework == "langchain" else "AgentOrchestrator",
        "framework": settings.agent_framework,
        "framework_dependencies_installed": langchain_installed and langchain_ollama_installed,
        "agents": [
            {
                "name": "Specification Retrieval Agent",
                "framework": "LangChain create_agent" if settings.agent_framework == "langchain" else "Custom Python",
                "role": "Calls a database-backed retrieval tool to fetch detailed phone specifications and source evidence.",
            },
            {
                "name": "Product Review Agent",
                "framework": "LangChain create_agent" if settings.agent_framework == "langchain" else "Custom Python",
                "role": "Receives the specification agent handoff, fetches the review evidence tool, and generates a balanced product review.",
            },
        ],
        "workflow": [
            "Specification Retrieval Agent retrieves records using SQLAlchemy and BM25-backed SpecificationAgent.",
            "The specification evidence is passed to the Product Review Agent.",
            "Product Review Agent obtains a second evidence brief and generates a source-grounded review with the local Ollama model.",
            "If optional framework dependencies or Ollama are unavailable, the API falls back to the existing custom/rule-based review.",
        ],
        "retrieval": "BM25 lexical retrieval over normalized phone fields and all stored specification rows",
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.ollama_model if settings.llm_provider in {"auto", "ollama"} else None,
            "enabled": settings.llm_provider != "none",
            "agent_framework": settings.agent_framework,
        },
    }
