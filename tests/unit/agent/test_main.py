"""agent/main.py: one chat message in, a stream of events out (with a fake model, no Bedrock)."""

import asyncio
import logging

import pytest
from bedrock_agentcore.runtime import RequestContext
from botocore.exceptions import ClientError

from agent import main
from agent.session import Sessions
from agent.tools import build_tools
from api.services import chat_quota
from tests.unit.agent.test_claims import token
from tests.unit.api.conftest import NEW

SARA = "customer-sub-1"
HERE = {"lat": NEW["lat"], "lng": NEW["lng"]}


class FakeAgent:
    """Plays a script: each step is an event dict, a callable(session) (e.g. a tool call), or an exception."""

    def __init__(self, session, script):
        self.session, self.script, self.calls = session, script, []

    async def stream_async(self, message, limits=None):
        self.calls.append((message, limits))
        for step in self.script:
            if isinstance(step, BaseException):
                raise step
            if callable(step):
                step(self.session)
                continue
            if step == "sleep":
                await asyncio.sleep(10)
                continue
            yield step


@pytest.fixture
def agent_script(monkeypatch, ddb, clock):
    """Replace the real agent with FakeAgent; set `script[:]` to choose what the 'model' does."""
    script: list = [{"data": "Hello"}, {"result": None}]
    made: list[FakeAgent] = []

    def factory(session):
        made.append(FakeAgent(session, script))
        return made[-1]

    monkeypatch.setattr(main, "sessions", Sessions(factory=factory))
    return script, made


def run(coro):
    """Run on a private event loop. (asyncio.run would clear the thread's current loop afterwards, which breaks
    later tests that use Mangum's asyncio.get_event_loop().)"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def ctx(groups=("customer",), sub=SARA, session_id="chat-123456789012345678901234567890"):
    headers = {"Authorization": "Bearer " + token({"sub": sub, "cognito:groups": list(groups)})}
    return RequestContext(session_id=session_id, request_headers=headers)


def chat(payload, context=None):
    async def collect():
        return [e async for e in main.invoke(payload, context or ctx())]

    return run(collect())


def types(events):
    return [e["type"] for e in events]


def test_happy_path_streams_text(agent_script):
    script, made = agent_script
    script[:] = [{"data": "Hi "}, {"data": "<thinking>plan</thinking>there"}, {"result": None}]
    events = chat({"message": "  hello  ", **HERE})
    assert events == [
        {"type": "quota", "left": 9},
        {"type": "text", "delta": "Hi "},
        {"type": "text", "delta": "there"},
        {"type": "done"},
    ]
    assert made[0].calls == [("hello\n\n[Reply in English.]", {"turns": main.MAX_TURNS})]  # trimmed + language note
    assert made[0].session.spot.lat == NEW["lat"]


def test_tool_status_once_per_tool_and_draft_at_the_end(agent_script, shop):
    script, _ = agent_script

    def draft(session):
        tools = {t.tool_name: t for t in build_tools(session)}
        tools["draft_cart"](restaurant_id=shop["rid"], items=[{"itemId": shop["burger"], "qty": 2}])

    use = {"toolUseId": "t1", "name": "draft_cart", "input": {}}
    script[:] = [{"current_tool_use": use}, {"current_tool_use": use}, draft, {"data": "Review it"}, {"result": None}]
    events = chat({"message": "add 2 burgers", **HERE})
    assert types(events) == ["quota", "status", "text", "draft", "done"]
    assert events[1] == {"type": "status", "tool": "draft_cart"}
    d = events[3]
    assert d["restaurant"]["id"] == shop["rid"] and d["lines"][0]["qty"] == 2 and d["totalHalalas"] == 5000


def test_draft_is_per_message(agent_script, shop):
    script, _ = agent_script
    draft = lambda s: setattr(s, "pending_draft", {"restaurant": {}, "lines": [], "totalHalalas": 0})  # noqa: E731
    script[:] = [draft, {"result": None}]
    assert "draft" in types(chat({"message": "add", **HERE}))
    script[:] = [{"data": "ok"}, {"result": None}]
    assert "draft" not in types(chat({"message": "thanks", **HERE}))


@pytest.mark.parametrize("groups", [("owner",), ("cashier",), ()])
def test_only_customers(agent_script, groups):
    assert chat({"message": "hi"}, ctx(groups=groups)) == [{"type": "error", "code": "not_customer"}]
    assert chat_quota.peek(SARA) == 10


def test_no_token():
    assert chat({"message": "hi"}, RequestContext(session_id="x", request_headers={})) == [
        {"type": "error", "code": "not_customer"}
    ]


@pytest.mark.parametrize("message", [None, "", "   ", 5, "x" * 501])
def test_invalid_message_not_counted(agent_script, message):
    assert chat({"message": message}) == [{"type": "error", "code": "invalid_message"}]
    assert chat_quota.peek(SARA) == 10


def test_quota_exceeded(agent_script, monkeypatch):
    monkeypatch.setenv("CHAT_DAILY_LIMIT", "1")
    assert types(chat({"message": "one"})) == ["quota", "text", "done"]
    assert chat({"message": "two"}) == [{"type": "quota", "left": 0}, {"type": "error", "code": "quota_exceeded"}]


@pytest.mark.parametrize(
    "payload",
    [{}, {"lat": "25.3", "lng": 49.5}, {"lat": 51.5, "lng": -0.12}, {"lat": True, "lng": 49.5}, {"lat": float("nan"), "lng": 49.5}],
)
def test_bad_or_missing_spot_means_no_spot(agent_script, payload):
    _, made = agent_script
    chat({"message": "hi", **payload})
    assert made[0].session.spot is None


def test_busy_while_previous_message_runs(agent_script):
    script, _ = agent_script
    script[:] = ["sleep"]

    async def both():
        first = asyncio.ensure_future(_collect({"message": "one"}))
        await asyncio.sleep(0.05)
        second = await _collect({"message": "two"})
        first.cancel()
        return second

    assert run(both()) == [{"type": "error", "code": "busy"}]
    assert chat_quota.peek(SARA) == 9  # only the first was counted


async def _collect(payload):
    return [e async for e in main.invoke(payload, ctx())]


@pytest.mark.parametrize(
    "exc, code",
    [
        (RuntimeError("boom secret details"), "failed"),
        (ClientError({"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "ConverseStream"), "busy"),
        (type("ModelThrottledException", (Exception,), {})("x"), "busy"),
    ],
)
def test_failure_gives_the_message_back(agent_script, exc, code, caplog):
    script, made = agent_script
    script[:] = [{"data": "Partial "}, exc]
    with caplog.at_level(logging.INFO, logger="sumaat.agent"):
        events = chat({"message": "my secret question"})
    assert events[-2:] == [{"type": "quota", "left": 10}, {"type": "error", "code": code}]
    assert chat_quota.peek(SARA) == 10
    assert "boom" not in str(events) and "slow down" not in str(events)
    assert "my secret question" not in caplog.text and "boom" not in caplog.text
    # the half-finished conversation is dropped: the next message gets a fresh agent
    script[:] = [{"result": None}]
    chat({"message": "again"})
    assert len(made) == 2


def test_timeout_gives_the_message_back(agent_script, monkeypatch):
    script, _ = agent_script
    script[:] = ["sleep"]
    monkeypatch.setattr(main, "TIMEOUT_SECONDS", 0.05)
    assert chat({"message": "hi"})[-1] == {"type": "error", "code": "failed"}
    assert chat_quota.peek(SARA) == 10


def test_success_log_has_no_text_or_ids(agent_script, caplog):
    script, _ = agent_script
    script[:] = [{"current_tool_use": {"toolUseId": "t", "name": "get_menu"}}, {"data": "Answer"}, {"result": None}]
    with caplog.at_level(logging.INFO, logger="sumaat.agent"):
        chat({"message": "private words"})
    assert "outcome=ok" in caplog.text and "tools=get_menu" in caplog.text
    assert "private words" not in caplog.text and SARA not in caplog.text and "Answer" not in caplog.text


def test_session_memory_kept_between_messages(agent_script):
    _, made = agent_script
    chat({"message": "one"})
    chat({"message": "two"})
    assert len(made) == 1 and [m.split("\n")[0] for m, _ in made[0].calls] == ["one", "two"]


@pytest.mark.parametrize(
    "message, lang, note",
    [("وش عندكم؟", "en", "Arabic"), ("menu please", "ar", "English"), ("2", "ar", "Arabic"), ("2", None, "English")],
)
def test_reply_language_note(agent_script, message, lang, note):
    _, made = agent_script
    chat({"message": message, "lang": lang})
    assert made[0].calls[0][0].endswith(f"[Reply in {note}.]")


def test_reply_uses_western_digits(agent_script):
    script, _ = agent_script
    script[:] = [{"data": "السعر ١٥ ريال × ٢"}, {"result": None}]
    texts = [e["delta"] for e in chat({"message": "كم؟"}) if e["type"] == "text"]
    assert "".join(texts) == "السعر 15 ريال × 2"
