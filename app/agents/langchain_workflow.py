from __future__ import annotations

import json
from contextlib import nullcontext
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agents.review_agent import ReviewAgent
from app.agents.specification_agent import SpecificationAgent
from app.config import settings
from app.models import Phone
from app.services.catalog import phone_to_document


class LangChainMultiAgentWorkflow:
    """Two-role LangChain workflow: specification retrieval -> review generation.

    The two agents are built with LangChain's current ``create_agent`` API and
    share a local Ollama chat model. Each agent has a narrow database-backed
    tool; the review agent receives the specification agent's output before it
    writes the final, source-grounded review.
    """

    def __init__(
        self,
        db: Session,
        *,
        agent_factory: Callable[..., Any] | None = None,
        model_factory: Callable[..., Any] | None = None,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.db = db
        # Production callers pass SessionLocal so each tool call owns its own
        # session even if LangGraph executes synchronous tools in a worker.
        # Unit tests can omit this and reuse their isolated in-memory session.
        self.session_factory = session_factory or (lambda: nullcontext(self.db))
        if agent_factory is None or model_factory is None:
            try:
                from langchain.agents import create_agent
                from langchain_ollama import ChatOllama
            except ImportError as exc:
                raise RuntimeError(
                    "LangChain agent dependencies are missing. Run: "
                    "python -m pip install -r requirements-addons.txt"
                ) from exc
            agent_factory = agent_factory or create_agent
            model_factory = model_factory or ChatOllama

        self.model = model_factory(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.15,
        )
        self.specification_agent = agent_factory(
            model=self.model,
            tools=[self.retrieve_phone_specifications],
            system_prompt=(
                "You are the Specification Retrieval Agent for a Samsung phone catalogue. "
                "You MUST call retrieve_phone_specifications before answering. Return only "
                "facts present in the database tool output. Preserve units and distinguish "
                "measured battery tests from battery capacity. Include source labels and URLs."
            ),
            name="samsung_specification_agent",
        )
        self.review_agent = agent_factory(
            model=self.model,
            tools=[self.retrieve_review_evidence],
            system_prompt=(
                "You are the Product Review Agent. You MUST call retrieve_review_evidence "
                "before generating a review. Use the specification agent's handoff plus the "
                "database evidence only. Produce a balanced detailed review covering display, "
                "performance, cameras, battery, software, price evidence when recorded, "
                "strengths, limitations, and missing information. Never invent test results, "
                "current market prices, or subjective quality claims unsupported by evidence. "
                "Cite provided source labels such as [S1]."
            ),
            name="samsung_product_review_agent",
        )

    def retrieve_phone_specifications(self, query: str) -> str:
        """Retrieve relevant Samsung phone specifications from the SQL database."""
        with self.session_factory() as db:
            result = SpecificationAgent(db).run(query)
            if not result.phones or not result.evidence.strip():
                return "No matching phone specification record was found in the database."
            return result.evidence

    def retrieve_review_evidence(self, phone_slug: str) -> str:
        """Fetch full database-backed evidence and limitations for one phone slug."""
        with self.session_factory() as db:
            phone = db.scalar(
                select(Phone)
                .options(selectinload(Phone.specifications), selectinload(Phone.prices))
                .where(Phone.slug == phone_slug)
            )
            if phone is None:
                return f"No phone exists with slug {phone_slug!r}."
            deterministic_review = ReviewAgent().generate(phone, include_limitations=True)
            payload = {
                "phone": phone.name,
                "specification_evidence": phone_to_document(phone),
                "rule_based_strengths": deterministic_review["strengths"],
                "rule_based_considerations": deterministic_review["considerations"],
                "source_url": phone.source_url,
                "data_quality": phone.data_quality,
            }
            return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    @staticmethod
    def _last_ai_text(result: Any) -> str:
        messages = result.get("messages", []) if isinstance(result, dict) else []
        for message in reversed(messages):
            message_type = getattr(message, "type", None)
            if message_type not in {"ai", "assistant"} and message.__class__.__name__ != "AIMessage":
                continue
            content = getattr(message, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                text_parts = [
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and isinstance(part.get("text"), str)
                ]
                joined = "\n".join(part for part in text_parts if part.strip()).strip()
                if joined:
                    return joined
        raise RuntimeError("LangChain agent completed without a textual assistant response.")

    def generate_review(self, phone_slug: str, include_limitations: bool = True) -> dict[str, str]:
        phone = self.db.scalar(select(Phone).where(Phone.slug == phone_slug))
        if phone is None:
            raise LookupError(f"Phone {phone_slug!r} was not found.")

        specification_result = self.specification_agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Retrieve the full stored specifications and source evidence for "
                            f"{phone.name} (slug: {phone_slug}). Include camera, display, platform, "
                            "memory, battery tests, and any recorded price observations."
                        ),
                    }
                ]
            }
        )
        specification_handoff = self._last_ai_text(specification_result)

        review_result = self.review_agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Generate a detailed balanced product review for {phone.name}. "
                            f"Phone slug: {phone_slug}. Include limitations: {include_limitations}.\n\n"
                            "Handoff from Specification Retrieval Agent:\n"
                            f"{specification_handoff}\n\n"
                            "Now call retrieve_review_evidence for the same slug and combine the "
                            "verified facts from both agents into the final review."
                        ),
                    }
                ]
            }
        )
        review_text = self._last_ai_text(review_result)
        return {
            "review": review_text,
            "specification_agent_output": specification_handoff,
            "review_agent_output": review_text,
        }
