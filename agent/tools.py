"""The Strands tools the model can call, bound to one chat session (its map spot and its pending draft).

Thin wrappers: the logic and all checks live in agent/catalog.py. Docstrings are what the model reads.
Return values are dicts; Strands sends them to the model as JSON.
"""

from typing import TYPE_CHECKING

from strands import tool

from agent import catalog

if TYPE_CHECKING:
    from agent.session import ChatSession


def build_tools(session: "ChatSession") -> list:
    @tool
    def find_restaurants(radius_km: float = 4.0, open_now_only: bool = False) -> dict:
        """Find restaurants near the spot the customer picked on the map, nearest first.

        Each restaurant has a status: "open", "paused" (not taking orders now) or "closed" (with opensAt).

        Args:
            radius_km: Search radius in km, 0.5 to 4. Default 4.
            open_now_only: True to list only restaurants taking orders right now.
        """
        if session.spot is None:
            return {"error": "no_location"}
        return catalog.find_restaurants(session.spot, radius_km, open_now_only)

    @tool
    def search_dishes(
        category: str | None = None,
        diet_tags: list[str] | None = None,
        max_calories: int | None = None,
        max_price_sar: float | None = None,
        open_now_only: bool = False,
    ) -> dict:
        """Search dishes across ALL restaurants near the customer's map spot in one call. Prefer this for any
        dish request ("something vegetarian under 20 SAR", "desserts", "spicy food near me").

        Each dish includes its restaurant (name, distanceKm, status open/paused/closed, opensAt).
        Results: nearest restaurant first, cheapest dish first. All given filters must match.

        Args:
            category: Optional menu category, e.g. "Desserts" (see list_categories).
            diet_tags: Optional tags the dish must have: vegetarian, vegan, gluten_free, dairy_free,
                high_protein, spicy.
            max_calories: Optional calorie limit (dishes with unknown calories are left out).
            max_price_sar: Optional maximum price in SAR.
            open_now_only: True to include only restaurants taking orders right now.
        """
        if session.spot is None:
            return {"error": "no_location"}
        return catalog.search_dishes(session.spot, category, diet_tags, max_calories, max_price_sar, open_now_only)

    @tool
    def get_menu(
        restaurant_id: str,
        category: str | None = None,
        diet_tags: list[str] | None = None,
        max_calories: int | None = None,
        max_price_sar: float | None = None,
    ) -> dict:
        """Get ONE restaurant's available dishes (prices in SAR, VAT included). All given filters must match.
        Use it when the customer asks about a specific restaurant; for dishes across restaurants use search_dishes.

        Args:
            restaurant_id: The restaurant id from find_restaurants.
            category: Optional menu category, e.g. "Mains" (see list_categories).
            diet_tags: Optional tags the dish must have: vegetarian, vegan, gluten_free, dairy_free,
                high_protein, spicy.
            max_calories: Optional calorie limit (dishes with unknown calories are left out).
            max_price_sar: Optional maximum price in SAR.
        """
        return catalog.get_menu(restaurant_id, category, diet_tags, max_calories, max_price_sar)

    @tool
    def list_categories() -> dict:
        """List the menu categories, in menu order."""
        return catalog.list_categories()

    @tool
    def draft_cart(restaurant_id: str, items: list[dict]) -> dict:
        """Prepare a cart draft for the customer to review. Use ONLY when the customer asks for it or agrees.

        This does not place an order. The customer sees the draft with an "Add to cart" button.
        All dishes must come from the same restaurant, which must be open.

        Args:
            restaurant_id: The restaurant id.
            items: The dishes, e.g. [{"itemId": "<dish id from search_dishes or get_menu>", "qty": 2}]. qty 1 to 20.
        """
        result = catalog.draft_cart(restaurant_id, items)
        if "draft" in result:
            session.pending_draft = result["draft"]
        return result

    return [find_restaurants, search_dishes, get_menu, list_categories, draft_cart]
