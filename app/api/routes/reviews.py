from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.langchain_workflow import LangChainMultiAgentWorkflow
from app.agents.review_agent import ReviewAgent
from app.config import settings
from app.database import SessionLocal, get_db
from app.models import Phone
from app.schemas import ReviewRequest, ReviewResponse
from app.services.catalog import phone_to_document
from app.services.llm import OllamaClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reviews", tags=["Product reviews"])


async def _ollama_model_is_available() -> bool:
    """Avoid starting a LangChain agent run when the configured local model is offline."""
    if settings.llm_provider == "none":
        return False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(settings.ollama_base_url.rstrip("/") + "/api/tags")
            response.raise_for_status()
            payload = response.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        configured = settings.ollama_model
        return any(
            item.get("name") == configured
            or (isinstance(item.get("name"), str) and item["name"].split(":", 1)[0] == configured.split(":", 1)[0])
            for item in models
            if isinstance(item, dict)
        )
    except (httpx.HTTPError, ValueError, TypeError):
        return False


@router.post("/{slug}", response_model=ReviewResponse, summary="Generate a specification-based product review")
async def generate_review(slug: str, payload: ReviewRequest, db: Session = Depends(get_db)):
    phone = db.scalar(select(Phone).where(Phone.slug == slug))
    if phone is None:
        raise HTTPException(status_code=404, detail=f"Phone '{slug}' was not found.")

    result = ReviewAgent().generate(phone, include_limitations=payload.include_limitations)
    generation_mode = "rule_based"

    if settings.agent_framework == "langchain" and await _ollama_model_is_available():
        try:
            with SessionLocal() as agent_db:
                workflow = LangChainMultiAgentWorkflow(agent_db, session_factory=SessionLocal)
                multi_agent_result = await asyncio.wait_for(
                    workflow.agenerate_review(slug, payload.include_limitations),
                    timeout=settings.agent_total_timeout_seconds,
                )
            result["review"] = multi_agent_result["review"]
            generation_mode = "langchain_multi_agent"
        except asyncio.TimeoutError:
            logger.error(
                "LangChain review exceeded the %.1f-second request deadline for %s; returning deterministic review.",
                settings.agent_total_timeout_seconds,
                slug,
            )
        except Exception as exc:  # Keep API usable if optional LangChain/Ollama is not ready.
            logger.warning("LangChain multi-agent review unavailable; returning deterministic review: %s", exc)

    # Avoid making a second unbounded Ollama request after a LangChain timeout.
    # The deterministic review is returned promptly and explicitly reports rule_based.
    if generation_mode == "rule_based" and settings.agent_framework != "langchain":
        generated = await OllamaClient().answer(
            query=(
                f"Write a balanced, detailed review of {phone.name}. Explain its display, cameras, "
                "battery, performance, key advantages and limitations. Do not invent missing facts. "
                "Use only the supplied evidence and cite source labels."
            ),
            evidence=f"[S1]\n{phone_to_document(phone)}",
        )
        if generated:
            result["review"] = generated
            generation_mode = "ollama_rag"

    return {
        "phone": phone.name,
        **result,
        "generation_mode": generation_mode,
        "source": {
            "title": phone.name,
            "source": phone.source_name,
            "url": phone.source_url,
            "data_quality": phone.data_quality,
        },
    }
