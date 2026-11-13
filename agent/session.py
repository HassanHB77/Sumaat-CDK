"""Chat sessions: one Strands agent (with its conversation memory) per chat.

AgentCore Runtime runs each session id in its own microVM, so normally a process holds one session. The store
still copes with several: a session belongs to the customer (sub) who started it, sits idle for at most
15 minutes, and at most MAX_SESSIONS are kept. Nothing is written to disk or a database: when a session is
dropped, its conversation is gone.
"""

import asyncio
import os
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from agent.catalog import Spot

IDLE_SECONDS = 15 * 60
MAX_SESSIONS = 50
WINDOW_MESSAGES = 20  # conversation memory (user + assistant + tool messages)
DEFAULT_MODEL_ID = "us.amazon.nova-2-lite-v1:0"


@dataclass
class ChatSession:
    sub: str
    spot: Spot | None = None
    pending_draft: dict | None = None
    agent: Any = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_used: float = field(default_factory=time.monotonic)


def build_model():
    from strands.models import BedrockModel

    config: dict[str, Any] = {
        "model_id": os.environ.get("MODEL_ID", DEFAULT_MODEL_ID),
        "temperature": 0.3,
        "max_tokens": 800,
    }
    if os.environ.get("GUARDRAIL_ID"):
        config["guardrail_id"] = os.environ["GUARDRAIL_ID"]
        config["guardrail_version"] = os.environ.get("GUARDRAIL_VERSION", "DRAFT")
        # Check the reply BEFORE each piece streams out, so blocked text never flashes on screen.
        config["guardrail_stream_processing_mode"] = "sync"
    return BedrockModel(region_name=os.environ.get("AWS_REGION", "us-east-1"), **config)


def build_agent(session: ChatSession):
    """The real Strands agent for a session. Tests replace this function with a fake."""
    from strands import Agent
    from strands.agent.conversation_manager import SlidingWindowConversationManager

    from agent.prompt import SYSTEM_PROMPT
    from agent.tools import build_tools

    return Agent(
        model=build_model(),
        tools=build_tools(session),
        system_prompt=SYSTEM_PROMPT,
        conversation_manager=SlidingWindowConversationManager(window_size=WINDOW_MESSAGES),
        callback_handler=None,  # don't print the conversation to stdout (= the logs)
    )


class Sessions:
    def __init__(self, factory=None):
        self._factory = factory
        self._items: OrderedDict[str, ChatSession] = OrderedDict()

    def get(self, session_id: str, sub: str) -> ChatSession:
        """The caller's session for this id; a new one if it's unknown, idle too long, or someone else's."""
        now = time.monotonic()
        self._drop_idle(now)
        s = self._items.get(session_id)
        if s is None or s.sub != sub:
            s = ChatSession(sub=sub)
            s.agent = (self._factory or build_agent)(s)
            self._items[session_id] = s
        self._items.move_to_end(session_id)
        s.last_used = now
        while len(self._items) > MAX_SESSIONS:
            self._items.popitem(last=False)
        return s

    def drop(self, session_id: str) -> None:
        self._items.pop(session_id, None)

    def _drop_idle(self, now: float) -> None:
        for sid in [sid for sid, s in self._items.items() if now - s.last_used > IDLE_SECONDS and not s.lock.locked()]:
            del self._items[sid]

    def __len__(self) -> int:
        return len(self._items)
