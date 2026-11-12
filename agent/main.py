"""Agent entrypoint on Bedrock AgentCore Runtime.

SPIKE (Step 9, piece 0): an echo agent that proves the path
    browser -> CloudFront /agent/chat -> AgentCore (Cognito JWT check) -> this container -> SSE stream back.
No model yet. Piece 2 replaces `invoke` with the real Strands agent; the event shapes stay the same:
    {"type":"text","delta":...}  {"type":"error","code":...}  {"type":"done"}
"""

import asyncio
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext

from agent.claims import caller_from

log = logging.getLogger("sumaat.agent")
app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload: dict, context: RequestContext):
    caller = caller_from(context.request_headers)
    if caller is None or not caller.is_customer:
        log.info("chat refused: not_customer")  # no ids, no text
        yield {"type": "error", "code": "not_customer"}
        return
    message = str((payload or {}).get("message", ""))[:500]
    # Echo word by word with a small pause, so we can SEE the stream arrive in pieces through CloudFront.
    for word in f"echo ({len(message)} chars): {message}".split(" "):
        yield {"type": "text", "delta": word + " "}
        await asyncio.sleep(0.2)
    yield {"type": "done"}


if __name__ == "__main__":
    app.run()  # http://localhost:8080/invocations (POST) and /ping
