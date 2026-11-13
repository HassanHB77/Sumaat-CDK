"""Agent entrypoint on Bedrock AgentCore Runtime: one customer chat message in, a stream of events out.

AgentCore has already checked the Cognito access token. Then, per message:
  1. the caller must be a customer                          -> else error not_customer
  2. the message must be 1-500 characters                   -> else error invalid_message
  3. one message at a time per chat                         -> else error busy (not counted)
  4. take one message from today's allowance (10/day)       -> quota {left} | error quota_exceeded
  5. run the Strands agent (Nova 2 Lite + tools), streaming -> status {tool} / text {delta}
  6. if the assistant drafted a cart                        -> draft {...}
  7.                                                         -> done
If the model or AWS fails, the message is given back and the customer gets error busy|failed (never the
exception text). Logs carry outcome, timing, tool names and token counts only: no message text, no ids.
"""

import asyncio
import logging
import math
import time
from typing import Any

from botocore.exceptions import ClientError
from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext

from agent.catalog import Spot
from agent.claims import caller_from
from agent.session import Sessions
from agent.text import ThinkingFilter, reply_language, western_digits
from api.services import chat_quota

logging.basicConfig(level=logging.WARNING)  # libraries: warnings only (they may log request details at INFO)
log = logging.getLogger("sumaat.agent")
log.setLevel(logging.INFO)

MAX_MESSAGE = 500
TIMEOUT_SECONDS = 50  # CloudFront waits up to 60 s
MAX_TURNS = 8  # model calls per message (each tool round is one)
BUSY_CODES = {"ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException", "TooManyRequestsException"}
# Saudi Arabia, roughly: anything outside means "no spot" (the model then asks the customer to pick one).
LAT_RANGE, LNG_RANGE = (16.0, 33.0), (34.0, 56.0)

app = BedrockAgentCoreApp()
sessions = Sessions()


def error(code: str) -> dict:
    return {"type": "error", "code": code}


def spot_from(payload: dict) -> Spot | None:
    lat, lng = payload.get("lat"), payload.get("lng")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (lat, lng)):
        return None
    if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LNG_RANGE[0] <= lng <= LNG_RANGE[1]):
        return None
    return Spot(float(lat), float(lng))


def _is_busy(e: BaseException) -> bool:
    if type(e).__name__ == "ModelThrottledException":
        return True
    if isinstance(e, ClientError):
        return e.response.get("Error", {}).get("Code") in BUSY_CODES
    return isinstance(e.__cause__, BaseException) and _is_busy(e.__cause__)


def _usage(agent: Any) -> tuple[int, int]:
    """Tokens used so far by this chat's agent (Strands keeps a running total per agent)."""
    try:
        usage = agent.event_loop_metrics.accumulated_usage
        return int(usage.get("inputTokens", 0)), int(usage.get("outputTokens", 0))
    except (AttributeError, TypeError, ValueError):
        return 0, 0


@app.entrypoint
async def invoke(payload: dict, context: RequestContext):
    started = time.monotonic()
    caller = caller_from(context.request_headers)
    if caller is None or not caller.is_customer:
        log.info("chat outcome=not_customer")
        yield error("not_customer")
        return

    payload = payload if isinstance(payload, dict) else {}
    message = payload.get("message")
    message = message.strip() if isinstance(message, str) else ""
    if not 1 <= len(message) <= MAX_MESSAGE:
        log.info("chat outcome=invalid_message")
        yield error("invalid_message")
        return

    session_id = context.session_id or f"no-session-{caller.sub}"
    session = sessions.get(session_id, caller.sub)
    if session.lock.locked():
        log.info("chat outcome=busy_session")
        yield error("busy")
        return

    async with session.lock:
        try:
            left = chat_quota.use_one(caller.sub)
        except chat_quota.QuotaExceeded:
            log.info("chat outcome=quota_exceeded")
            yield {"type": "quota", "left": 0}
            yield error("quota_exceeded")
            return
        yield {"type": "quota", "left": left}

        session.spot = spot_from(payload)
        session.pending_draft = None
        # The model alone often answers in Arabic (the tool results are full of Arabic names), so say it per message.
        prompt = f"{message}\n\n[Reply in {reply_language(message, payload.get('lang'))}.]"
        tools_used: list[str] = []
        seen_tool_ids: set[str] = set()
        clean = ThinkingFilter()
        result = None
        tokens_before = _usage(session.agent)
        try:
            async with asyncio.timeout(TIMEOUT_SECONDS):
                async for event in session.agent.stream_async(prompt, limits={"turns": MAX_TURNS}):
                    if "data" in event:
                        text = western_digits(clean.feed(event["data"]))
                        if text:
                            yield {"type": "text", "delta": text}
                    elif "current_tool_use" in event:
                        use = event["current_tool_use"] or {}
                        tool_id, name = use.get("toolUseId"), use.get("name")
                        if tool_id and name and tool_id not in seen_tool_ids:
                            seen_tool_ids.add(tool_id)
                            tools_used.append(name)
                            yield {"type": "status", "tool": name}
                    elif "result" in event:
                        result = event["result"]
            rest = western_digits(clean.flush())
            if rest:
                yield {"type": "text", "delta": rest}
        except Exception as e:  # model / AWS / timeout: give the message back, keep details out of the reply
            chat_quota.give_back(caller.sub)
            sessions.drop(session_id)  # the conversation may be half-written; start clean next time
            code = "busy" if _is_busy(e) else "failed"
            log.warning(
                "chat outcome=%s error=%s ms=%d tools=%s",
                code, type(e).__name__, (time.monotonic() - started) * 1000, ",".join(tools_used),
            )
            yield {"type": "quota", "left": left + 1}
            yield error(code)
            return

        if session.pending_draft:
            yield {"type": "draft", **session.pending_draft}
        tokens_after = _usage(session.agent)
        log.info(
            "chat outcome=ok ms=%d tools=%s draft=%s tokens_in=%d tokens_out=%d stop=%s",
            (time.monotonic() - started) * 1000, ",".join(tools_used), bool(session.pending_draft),
            tokens_after[0] - tokens_before[0], tokens_after[1] - tokens_before[1],
            getattr(result, "stop_reason", None),
        )
        yield {"type": "done"}


if __name__ == "__main__":
    app.run()  # http://localhost:8080/invocations (POST) and /ping
