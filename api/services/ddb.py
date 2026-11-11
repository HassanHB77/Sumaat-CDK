"""Small DynamoDB helpers shared by services."""


def set_expression(changes: dict) -> dict:
    """Build update_item kwargs for "SET a = :a, b = :b".

    Uses placeholder names (#f0, #f1...) so any attribute name is safe, including reserved words like `name`.
    Returns UpdateExpression, ExpressionAttributeNames and ExpressionAttributeValues; merge extra
    condition values into ExpressionAttributeValues yourself.
    """
    if not changes:
        raise ValueError("changes must not be empty")
    keys = list(changes)
    return {
        "UpdateExpression": "SET " + ", ".join(f"#f{i} = :v{i}" for i in range(len(keys))),
        "ExpressionAttributeNames": {f"#f{i}": k for i, k in enumerate(keys)},
        "ExpressionAttributeValues": {f":v{i}": changes[k] for i, k in enumerate(keys)},
    }
