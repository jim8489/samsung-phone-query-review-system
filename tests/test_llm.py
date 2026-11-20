import asyncio

from app.config import settings
from app.services.llm import OllamaClient


class FakeResponse:
    def raise_for_status(self):
        return None

    @staticmethod
    def json():
        return {"message": {"content": "The Galaxy S23 has a 6.1-inch display. [S1]"}}


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get("timeout")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, json):
        assert url.endswith("/api/chat")
        assert json["model"] == settings.ollama_model
        assert json["stream"] is False
        assert "Retrieved catalogue evidence" in json["messages"][-1]["content"]
        return FakeResponse()


def test_ollama_client_generates_from_retrieved_evidence(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr("app.services.llm.httpx.AsyncClient", FakeAsyncClient)

    answer = asyncio.run(
        OllamaClient().answer(
            "What is the Galaxy S23 display size?",
            "[S1]\nPhone: Samsung Galaxy S23\nDisplay: 6.1 inches",
        )
    )

    assert answer == "The Galaxy S23 has a 6.1-inch display. [S1]"


def test_ollama_client_obeys_disabled_provider(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "none")
    answer = asyncio.run(OllamaClient().answer("question", "[S1] evidence"))
    assert answer is None
