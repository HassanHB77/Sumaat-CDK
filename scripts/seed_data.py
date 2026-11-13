"""Demo data: categories, customers, and the 15 FICTIONAL restaurants (in scripts/seed_restaurants.py).

Prices are whole halalas (100 halalas = 1 SAR). Calories are rough per-serving estimates.
"""

from scripts.seed_restaurants import RESTAURANTS

__all__ = ["CATEGORIES", "CUSTOMERS", "RESTAURANTS"]

# Menu categories owners can choose from, in MENU ORDER (stored as CONFIG/CATEGORIES: the set + displayOrder;
# extend the set later via CLI/console, new ones are listed last).
CATEGORIES = [
    "Breakfast", "Mains", "Grills", "Burgers", "Pizza", "Pasta", "Curries", "Sushi", "Noodles", "Seafood", "Bowls",
    "Sandwiches", "Mezze", "Salads", "Sides", "Kids", "Sweets", "Dates", "Juices", "Smoothies", "Drinks",
]

# Demo customers (fake emails and phones). Ordering needs a customer account (one role per account).
CUSTOMERS = [
    {"email": "sara@example.com", "name": "Sara Al-Qahtani", "phone": "+966500000301"},
    {"email": "omar@example.com", "name": "Omar Al-Harbi", "phone": "+966500000302"},
]

# Order numbers: no seed needed. Each restaurant starts at #1 every day (api/services/orders.py).
