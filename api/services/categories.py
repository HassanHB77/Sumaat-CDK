"""The fixed list of menu categories, stored in the table so it can be extended without a deploy.

Item: PK=CONFIG  SK=CATEGORIES  categories={string set}  displayOrder=[list]
  categories    what owners may choose (the rule)
  displayOrder  how menus list them (meal order); categories not in it go last, A-Z
Add one from the CLI (ADD on a set is a union, so repeating it is harmless):
  aws dynamodb update-item --table-name sumaat --region us-east-1 \\
    --key '{"PK":{"S":"CONFIG"},"SK":{"S":"CATEGORIES"}}' \\
    --update-expression "ADD categories :c" \\
    --expression-attribute-values '{":c":{"SS":["Soups"]}}'
"""

from api import aws
from api.errors import Invalid

KEY = {"PK": "CONFIG", "SK": "CATEGORIES"}


def allowed() -> set[str]:
    item = aws.table().get_item(Key=KEY).get("Item") or {}
    return set(item.get("categories", set()))


def ordered() -> list[str]:
    """Allowed categories in menu order: displayOrder first, then any others (e.g. added by CLI) A-Z."""
    item = aws.table().get_item(Key=KEY).get("Item") or {}
    names = set(item.get("categories", set()))
    order = [c for c in item.get("displayOrder", []) if c in names]
    return order + sorted(names - set(order))


def check(name: str) -> None:
    names = allowed()
    if not names:
        raise Invalid("Menu categories are not set up yet (CONFIG/CATEGORIES item is missing)")
    if name not in names:
        raise Invalid(f"Unknown category '{name}'. Allowed: {', '.join(sorted(names))}")
