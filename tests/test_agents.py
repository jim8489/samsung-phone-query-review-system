from app.agents.review_agent import ReviewAgent
from app.agents.specification_agent import SpecificationAgent
from app.models import Phone
from app.services.retriever import BM25Retriever


def test_bm25_retrieves_relevant_phone(db_session):
    phones = db_session.query(Phone).all()
    results = BM25Retriever().retrieve("Snapdragon 8 Gen 2 processor", phones, top_k=3)
    assert results
    assert "S23" in results[0].phone.name


def test_specification_agent_matches_two_explicit_models(db_session):
    result = SpecificationAgent(db_session).run("Compare Galaxy S23 and Galaxy S22 performance")
    names = [phone.name for phone in result.phones]
    assert result.intent == "comparison"
    assert names == ["Samsung Galaxy S23", "Samsung Galaxy S22"]
    assert "Snapdragon" in result.evidence


def test_review_agent_includes_limits_for_demo_record(db_session):
    phone = db_session.query(Phone).filter_by(slug="samsung-galaxy-s23").one()
    result = ReviewAgent().generate(phone)
    assert result["review"]
    assert result["strengths"]
    assert any("demo" in item.lower() for item in result["considerations"])


def test_specification_agent_does_not_confuse_capacity_with_battery_life(db_session):
    result = SpecificationAgent(db_session).run("Which Samsung phone has the best battery life?")
    assert result.intent == "best_battery_life"
    assert result.phones
    assert all(phone.active_use_score_minutes is None for phone in result.phones)
    assert all(phone.endurance_rating_hours is None for phone in result.phones)


def test_review_agent_preserves_test_result_source_link(db_session):
    phone = db_session.query(Phone).filter_by(slug="samsung-galaxy-s23").one()
    phone.test_source_url = "https://www.gsmarena.com/compare.php3?idPhone1=12082"
    result = ReviewAgent().generate(phone)
    assert "Measured test results" in result["review"]
    assert phone.test_source_url in result["review"]
