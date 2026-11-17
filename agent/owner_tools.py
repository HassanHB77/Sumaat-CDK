"""The Strands tools of the OWNER assistant, bound to one owner chat (its restaurant id comes from the server).

Thin wrappers around agent/owner_catalog.py. Docstrings are what the model reads.
"""

from typing import TYPE_CHECKING

from strands import tool

from agent import owner_catalog as oc

if TYPE_CHECKING:
    from agent.session import ChatSession

PERIOD_HELP = (
    "One of: today, yesterday, this_week, last_week, this_month, last_month. Days run 04:00-04:00 Riyadh time; "
    "weeks start on Sunday; months on the 1st."
)


def build_owner_tools(session: "ChatSession") -> list:
    rid = session.restaurant_id or ""

    @tool
    def order_summary(period: str = "today") -> dict:
        """Number of orders (served, open, rejected, cancelled) and sales in SAR for the owner's restaurant,
        with the previous period and the % change. Use it for "how many orders", "how much did we sell",
        "compared with last week".

        Args:
            period: today, yesterday, this_week, last_week, this_month or last_month.
        """
        return oc.order_summary(rid, period)

    @tool
    def dish_sales(dish: str, period: str = "this_week") -> dict:
        """How many of one dish were sold (and its sales in SAR) in a period, vs the previous period.
        The dish is matched by its English or Arabic name (part of the name is enough).

        Args:
            dish: The dish name as the owner wrote it, e.g. "kabsa" or "كبسة".
            period: today, yesterday, this_week, last_week, this_month or last_month.
        """
        return oc.dish_sales(rid, dish, period)

    @tool
    def best_sellers(period: str = "this_month", limit: int = 5) -> dict:
        """The best-selling dishes by quantity, and the slow dishes (visible dishes that sold least, 0 included).

        Args:
            period: today, yesterday, this_week, last_week, this_month or last_month.
            limit: How many dishes in each list, 1 to 10. Default 5.
        """
        return oc.best_sellers(rid, period, limit)

    @tool
    def prep_time(period: str = "this_week") -> dict:
        """Average and median minutes from accepting an order until it is ready, the fastest and slowest,
        vs the previous period.

        Args:
            period: today, yesterday, this_week, last_week, this_month or last_month.
        """
        return oc.prep_time(rid, period)

    @tool
    def busiest_times(period: str = "this_month") -> dict:
        """When orders come in: the busiest hours of the day (Riyadh time) and days of the week.

        Args:
            period: today, yesterday, this_week, last_week, this_month or last_month.
        """
        return oc.busiest_times(rid, period)

    @tool
    def rejections(period: str = "this_week") -> dict:
        """Orders the restaurant rejected (with the reasons) and orders customers cancelled, vs the previous period.

        Args:
            period: today, yesterday, this_week, last_week, this_month or last_month.
        """
        return oc.rejections(rid, period)

    return [order_summary, dish_sales, best_sellers, prep_time, busiest_times, rejections]
