"""agent/tools.py: the Strands tools use the chat's map spot and keep the draft for the reply."""

from agent.catalog import Spot
from agent.session import ChatSession
from agent.tools import build_tools
from tests.unit.api.conftest import NEW


def tools(session):
    return {t.tool_name: t for t in build_tools(session)}


def test_no_spot_means_no_location():
    assert tools(ChatSession(sub="sara"))["find_restaurants"]() == {"error": "no_location"}


def test_find_uses_the_session_spot(shop):
    s = ChatSession(sub="sara", spot=Spot(NEW["lat"], NEW["lng"]))
    res = tools(s)["find_restaurants"](radius_km=1)
    assert res["radiusKm"] == 1 and shop["rid"] in [r["id"] for r in res["restaurants"]]


def test_draft_is_kept_on_the_session(shop):
    s = ChatSession(sub="sara")
    res = tools(s)["draft_cart"](restaurant_id=shop["rid"], items=[{"itemId": shop["burger"], "qty": 2}])
    assert s.pending_draft == res["draft"] and s.pending_draft["totalHalalas"] == 5000


def test_refused_draft_is_not_kept(shop):
    s = ChatSession(sub="sara")
    tools(s)["draft_cart"](restaurant_id=shop["rid"], items=[{"itemId": "nope", "qty": 1}])
    assert s.pending_draft is None


def test_menu_and_categories(shop):
    t = tools(ChatSession(sub="sara"))
    assert t["get_menu"](restaurant_id=shop["rid"], max_price_sar=10)["count"] == 1
    assert "Mains" in t["list_categories"]()["categories"]


def test_search_dishes_needs_a_spot():
    assert tools(ChatSession(sub="sara"))["search_dishes"]() == {"error": "no_location"}


def test_search_dishes_uses_the_session_spot(shop):
    s = ChatSession(sub="sara", spot=Spot(NEW["lat"], NEW["lng"]))
    res = tools(s)["search_dishes"](max_price_sar=10)
    assert shop["fries"] in [d["id"] for d in res["dishes"]]
