from __future__ import annotations

from types import SimpleNamespace

from app.agents.langchain_workflow import LangChainMultiAgentWorkflow
from app.data.seed import slugify
from app.models import Phone


class FakeAgent:
    def __init__(self, name, tools):
        self.name = name
        self.tools = tools
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        user_text = payload["messages"][0]["content"]
        if self.name == "samsung_specification_agent":
            tool_output = self.tools[0](user_text)
            content = "Specification Agent handoff:\n" + tool_output
        else:
            slug = user_text.split("Phone slug:", 1)[1].split(".", 1)[0].strip()
            tool_output = self.tools[0](slug)
            content = "Detailed generated review based on:\n" + tool_output
        return {"messages": [SimpleNamespace(type="ai", content=content)]}


def test_langchain_workflow_coordinates_two_database_backed_agents(db_session):
    created = []

    def model_factory(**kwargs):
        return SimpleNamespace(**kwargs)

    def agent_factory(*, model, tools, system_prompt, name):
        agent = FakeAgent(name, tools)
        created.append({"agent": agent, "model": model, "system_prompt": system_prompt})
        return agent

    phone = db_session.query(Phone).filter(Phone.name == "Samsung Galaxy S23").one()
    workflow = LangChainMultiAgentWorkflow(
        db_session,
        agent_factory=agent_factory,
        model_factory=model_factory,
    )
    result = workflow.generate_review(phone.slug, include_limitations=True)

    assert [item["agent"].name for item in created] == [
        "samsung_specification_agent",
        "samsung_product_review_agent",
    ]
    assert "Samsung Galaxy S23" in result["specification_agent_output"]
    assert "Detailed generated review" in result["review"]
    assert "specification_evidence" in result["review_agent_output"]
    assert created[0]["agent"].tools[0].__name__ == "retrieve_phone_specifications"
    assert created[1]["agent"].tools[0].__name__ == "retrieve_review_evidence"


def test_missing_langchain_dependency_has_actionable_error(db_session, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "langchain.agents" or name == "langchain_ollama":
            raise ImportError("simulated missing optional package")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    try:
        LangChainMultiAgentWorkflow(db_session)
    except RuntimeError as exc:
        assert "requirements-addons.txt" in str(exc)
    else:
        raise AssertionError("Missing LangChain packages should produce a clear setup error.")
