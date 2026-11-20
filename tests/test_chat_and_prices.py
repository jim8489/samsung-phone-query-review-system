import asyncio

from app.agents.orchestrator import AgentOrchestrator
from app.models import Phone, PriceObservation


def test_chat_fallback_answers_camera_question(db_session):
    answer, mode, result = asyncio.run(
        AgentOrchestrator(db_session).answer("What are the camera specifications of the Galaxy S23?")
    )
    assert mode == "rag_fallback"
    assert "50 MP" in answer
    assert result.phones[0].name == "Samsung Galaxy S23"


def test_review_request_runs_review_agent_through_orchestrator(db_session):
    answer, mode, result = asyncio.run(
        AgentOrchestrator(db_session).answer("Please review the Galaxy S23")
    )
    assert mode == "rag_fallback"
    assert "specification-based review" in answer
    assert "Strengths" in answer and "Considerations" in answer
    assert result.intent == "review"


def test_price_observations_are_persisted_and_reflected(db_session):
    phone = db_session.query(Phone).filter_by(slug="samsung-galaxy-s23").one()
    db_session.add(PriceObservation(phone_id=phone.id, amount=85000, currency="BDT", source="Test retailer", is_current=True))
    phone.price_amount = 85000
    phone.price_currency = "BDT"
    db_session.commit()
    answer, _, result = asyncio.run(AgentOrchestrator(db_session).answer("What is the price of Galaxy S23?"))
    assert "BDT 85,000.00" in answer
    assert any(source["data_quality"] == "price_observation" and source["source"] == "Test retailer" for source in result.sources)


def test_battery_life_answer_discloses_when_measurements_are_missing(db_session):
    answer, _, result = asyncio.run(
        AgentOrchestrator(db_session).answer("Which Samsung phone has the longest battery life?")
    )
    assert result.intent == "best_battery_life"
    assert "cannot establish" in answer.lower()
    assert "mAh" in answer


def test_battery_life_answer_uses_measured_active_use_score(db_session):
    s23 = db_session.query(Phone).filter_by(slug="samsung-galaxy-s23").one()
    s22 = db_session.query(Phone).filter_by(slug="samsung-galaxy-s22").one()
    s23.active_use_score_minutes = 687
    s22.active_use_score_minutes = 615
    db_session.commit()
    answer, _, _ = asyncio.run(
        AgentOrchestrator(db_session).answer("Which Samsung phone has the longest battery life?")
    )
    assert "GSMArena measured active-use results" in answer
    assert "11:27h" in answer
    assert answer.index("Galaxy S23") < answer.index("Galaxy S22")


def test_chat_can_answer_a_specific_hardware_feature_from_raw_specs(db_session):
    phone = db_session.query(Phone).filter_by(slug="samsung-galaxy-s23").one()
    phone.raw_specs = {**phone.raw_specs, "Comms": {"NFC": "Yes", "Bluetooth": "5.3"}}
    db_session.commit()
    answer, _, result = asyncio.run(
        AgentOrchestrator(db_session).answer("Does the Galaxy S23 have NFC?")
    )
    assert result.intent == "feature"
    assert "NFC:** Yes" in answer


def test_chat_can_use_a_price_estimate_preserved_in_source_specs(db_session):
    phone = db_session.query(Phone).filter_by(slug="samsung-galaxy-s23").one()
    phone.raw_specs = {**phone.raw_specs, "Misc": {"Price": "$240.00 / £229.00 / €295.33"}}
    db_session.commit()
    answer, _, _ = asyncio.run(
        AgentOrchestrator(db_session).answer("What is the price of Galaxy S23?")
    )
    assert "GSMArena's stored specification page lists" in answer
    assert "$240.00" in answer
    assert "not a verified current local offer" in answer


def test_chat_cites_gsmarena_test_page_when_measured_battery_data_exists(db_session):
    phone = db_session.query(Phone).filter_by(slug="samsung-galaxy-s23").one()
    phone.active_use_score_minutes = 687
    phone.test_source_url = "https://www.gsmarena.com/compare.php3?idPhone1=12082"
    phone.raw_specs = {**phone.raw_specs, "Our Tests": {"Battery": "Active use score 11:27h"}}
    db_session.commit()

    answer, _, result = asyncio.run(
        AgentOrchestrator(db_session).answer("Which Samsung phone has the longest battery life?")
    )

    assert "11:27h" in answer
    assert any(source["url"] == phone.test_source_url for source in result.sources)
