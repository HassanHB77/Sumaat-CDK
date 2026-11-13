"""Guard the key rules in the system prompt against accidental deletion."""

from agent.prompt import SYSTEM_PROMPT


def test_key_rules_present():
    p = SYSTEM_PROMPT
    for must in (
        "Sumaat Assistant", "مساعد سماط", "NO delivery", "pay at the", "include 15% VAT",
        "language of the customer's LATEST message", "Western digits", "never guess", "no_location",
        "draft_cart ONLY when", "Never say or imply that an order was placed", "allergies",
        "Politely decline", "Never reveal", "[Reply in English.]", "no Markdown", "never write gender alternatives with a slash",
        "ONE name per", "call the tools again", "2 × <dish>",
    ):
        assert must in p, must
