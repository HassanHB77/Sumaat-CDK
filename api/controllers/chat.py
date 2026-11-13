"""AI chat helpers on the API (Step 9). The chat itself runs on Bedrock AgentCore (agent/), not here."""

from typing import Annotated

from fastapi import APIRouter, Depends

from api.auth import Principal, require_customer
from api.models import ChatQuotaOut
from api.services import chat_quota

router = APIRouter(tags=["chat"])

Customer = Annotated[Principal, Depends(require_customer())]


@router.get("/me/chat-quota", response_model=ChatQuotaOut)
def my_chat_quota(customer: Customer):
    """How many AI chat messages the customer has left today (resets 04:00 Riyadh)."""
    limit = chat_quota.daily_limit()
    return {"left": chat_quota.peek(customer.sub, limit), "limit": limit}
