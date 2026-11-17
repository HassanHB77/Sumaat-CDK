"""Guard the key rules in the system prompt against accidental deletion."""

from agent.prompt import SYSTEM_PROMPT


def test_key_rules_present():
    p = SYSTEM_PROMPT
    for must in (
        "Sumaat Assistant", "مساعد سماط", "NO delivery", "pay at the", "include 15% VAT",
        "language of the customer's LATEST message", "Western digits", "never guess", "no_location",
        "draft_cart ONLY when", "Never say or imply that an order was placed", "allergies",
        "Politely decline", "Never reveal", "[Reply in English.]", "no Markdown", "never write gender alternatives with a slash",
        "ONE name per", "call search_dishes ONCE", "do NOT call find_restaurants first", "unknown_category", "call the tools again", "2 × <dish>",
    ):
        assert must in p, must


def test_owner_prompt_names_only_real_pages_and_rules():
    from agent.prompt_owner import OWNER_PROMPT

    for page in ("Orders", "Menu", "Restaurant", "Cashiers"):
        assert page in OWNER_PROMPT
    assert "Never mention other pages" in OWNER_PROMPT
    assert "SERVED orders only" in OWNER_PROMPT and "Western digits" in OWNER_PROMPT
    assert "الطلبات المُسلَّمة" in OWNER_PROMPT  # the app's Arabic words
