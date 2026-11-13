"""agent/session.py: one agent per chat, owned by one customer, dropped when idle."""

import pytest

from agent import session as session_mod
from agent.session import IDLE_SECONDS, MAX_SESSIONS, Sessions


@pytest.fixture
def clock(monkeypatch):
    t = {"now": 1000.0}
    monkeypatch.setattr(session_mod.time, "monotonic", lambda: t["now"])
    return t


def store():
    return Sessions(factory=lambda s: object())


def test_same_chat_same_session(clock):
    s = store()
    a = s.get("chat-1", "sara")
    assert s.get("chat-1", "sara") is a and a.agent is not None


def test_someone_else_using_the_id_gets_a_fresh_session(clock):
    s = store()
    sara = s.get("chat-1", "sara")
    sara.pending_draft = {"x": 1}
    omar = s.get("chat-1", "omar")
    assert omar is not sara and omar.sub == "omar" and omar.pending_draft is None and omar.agent is not sara.agent


def test_idle_session_is_forgotten(clock):
    s = store()
    a = s.get("chat-1", "sara")
    clock["now"] += IDLE_SECONDS - 1
    assert s.get("chat-1", "sara") is a  # still within 15 min (and the clock restarts)
    clock["now"] += IDLE_SECONDS + 1
    assert s.get("chat-1", "sara") is not a


def test_at_most_max_sessions(clock):
    s = store()
    for n in range(MAX_SESSIONS + 5):
        s.get(f"chat-{n}", "sara")
    assert len(s) == MAX_SESSIONS


def test_drop(clock):
    s = store()
    a = s.get("chat-1", "sara")
    s.drop("chat-1")
    assert s.get("chat-1", "sara") is not a


def test_model_config(monkeypatch):
    monkeypatch.delenv("GUARDRAIL_ID", raising=False)
    m = session_mod.build_model()
    assert m.config["model_id"] == "us.amazon.nova-2-lite-v1:0" and "guardrail_id" not in m.config
    monkeypatch.setenv("GUARDRAIL_ID", "gr-1")
    monkeypatch.setenv("GUARDRAIL_VERSION", "3")
    m = session_mod.build_model()
    assert m.config["guardrail_id"] == "gr-1" and m.config["guardrail_version"] == "3"


def test_real_agent_has_the_four_tools_and_prompt():
    from agent.prompt import SYSTEM_PROMPT
    from agent.session import ChatSession

    agent = session_mod.build_agent(ChatSession(sub="sara"))
    assert set(agent.tool_names) == {"find_restaurants", "get_menu", "list_categories", "draft_cart"}
    assert agent.system_prompt == SYSTEM_PROMPT
