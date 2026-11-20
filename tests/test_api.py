from fastapi.testclient import TestClient

from app.main import app


def test_health_and_catalogue_endpoints():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["database"] == "connected"
        phones = client.get("/api/phones")
        assert phones.status_code == 200
        assert len(phones.json()) >= 10
        detail = client.get("/api/phones/samsung-galaxy-s23")
        assert detail.status_code == 200
        assert detail.json()["name"] == "Samsung Galaxy S23"
        assert "test_source_url" in detail.json()


def test_chat_api_returns_grounded_answer():
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"query": "What are the camera specifications of the Galaxy S23?"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "rag_fallback"
        assert "50 MP" in payload["answer"]
        assert payload["session_id"]


def test_compare_review_and_price_observation_endpoints():
    with TestClient(app) as client:
        comparison = client.get(
            "/api/phones/compare?slugs=samsung-galaxy-s23,samsung-galaxy-s22"
        )
        assert comparison.status_code == 200
        assert comparison.json()["models"] == ["Samsung Galaxy S23", "Samsung Galaxy S22"]

        review = client.post("/api/reviews/samsung-galaxy-s23", json={"include_limitations": True})
        assert review.status_code == 200
        assert "Samsung Galaxy S23" in review.json()["review"]
        assert review.json()["generation_mode"] == "rule_based"

        price = client.post(
            "/api/phones/samsung-galaxy-s23/prices",
            json={"amount": 85000, "currency": "BDT", "source": "Assessment test retailer"},
        )
        assert price.status_code == 201
        assert price.json()["currency"] == "BDT"

        detail = client.get("/api/phones/samsung-galaxy-s23")
        assert detail.status_code == 200
        assert len(detail.json()["price_observations"]) >= 1


def test_best_battery_endpoint_discloses_proxy_when_no_test_data_exists():
    with TestClient(app) as client:
        response = client.get("/api/phones/best-battery")
        assert response.status_code == 200
        payload = response.json()
        assert payload["metric"] == "battery capacity (mAh) — proxy only"
        assert "cannot establish" in payload["warning"]


def test_scraper_endpoint_validates_delay_and_deduplicates_models(monkeypatch):
    from app.api.routes import scraper as scraper_routes

    captured = {}

    def fake_run(models, delay):
        captured["models"] = models
        captured["delay"] = delay
        return {
            "attempted": len(models),
            "scraped": 0,
            "failed": len(models),
            "results": [
                {"model": model, "status": "failed", "message": "External network unavailable."}
                for model in models
            ],
        }

    monkeypatch.setattr(scraper_routes, "_run_scrape", fake_run)
    with TestClient(app) as client:
        invalid = client.post(
            "/api/scraper/run",
            json={"models": ["Galaxy S23"], "delay_seconds": 1},
        )
        assert invalid.status_code == 422

        valid = client.post(
            "/api/scraper/run",
            json={"models": ["Galaxy S23", "Galaxy S23", "Galaxy S24"], "delay_seconds": 2},
        )
        assert valid.status_code == 200
        assert valid.json()["attempted"] == 2
        assert captured["models"] == ["Galaxy S23", "Galaxy S24"]
        assert captured["delay"] == 2


def test_review_respects_explicit_llm_disable_setting(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "llm_provider", "none")
    monkeypatch.setattr(settings, "agent_framework", "langchain")
    with TestClient(app) as client:
        response = client.post(
            "/api/reviews/samsung-galaxy-s23",
            json={"include_limitations": True},
        )
    assert response.status_code == 200
    assert response.json()["generation_mode"] == "rule_based"


def test_langchain_review_timeout_returns_without_second_unbounded_llm_call(monkeypatch):
    import asyncio

    from app.api.routes import reviews as review_routes
    from app.config import settings

    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "agent_framework", "langchain")

    async def model_available():
        return True

    monkeypatch.setattr(review_routes, "_ollama_model_is_available", model_available)

    class TimeoutWorkflow:
        def __init__(self, *args, **kwargs):
            pass

        async def agenerate_review(self, *args, **kwargs):
            raise asyncio.TimeoutError

    monkeypatch.setattr(review_routes, "LangChainMultiAgentWorkflow", TimeoutWorkflow)
    with TestClient(app) as client:
        response = client.post(
            "/api/reviews/samsung-galaxy-s23",
            json={"include_limitations": True},
        )

    assert response.status_code == 200
    assert response.json()["generation_mode"] == "rule_based"
    assert "Samsung Galaxy S23" in response.json()["review"]
