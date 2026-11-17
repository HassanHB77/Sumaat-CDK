"""AI chat helpers on the API (Step 9). The chat itself runs on Bedrock AgentCore (agent/), not here."""

from typing import Annotated

from fastapi import APIRouter, Depends

from api.auth import Principal, require_groups
from api.models import ChatQuotaOut
from api.services import chat_quota

router = APIRouter(tags=["chat"])

ChatUser = Annotated[Principal, Depends(require_groups("customer", "owner"))]  # cashiers have no assistant


@router.get("/me/chat-quota", response_model=ChatQuotaOut)
def my_chat_quota(user: ChatUser):
    """How many AI chat messages the customer or owner has left today (resets 04:00 Riyadh)."""
    limit = chat_quota.daily_limit()
    return {"left": chat_quota.peek(user.sub, limit), "limit": limit}
