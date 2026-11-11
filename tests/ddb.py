"""Shared test helper: create the `sumaat` table in moto with the same keys/GSIs as infra/data_stack.py."""


def _gsi(n: int) -> dict:
    return {
        "IndexName": f"GSI{n}",
        "KeySchema": [
            {"AttributeName": f"GSI{n}PK", "KeyType": "HASH"},
            {"AttributeName": f"GSI{n}SK", "KeyType": "RANGE"},
        ],
        "Projection": {"ProjectionType": "ALL"},
    }


def create_table(ddb, name: str = "sumaat"):
    return ddb.create_table(
        TableName=name,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        AttributeDefinitions=[
            {"AttributeName": a, "AttributeType": "S"}
            for a in ("PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK")
        ],
        GlobalSecondaryIndexes=[_gsi(1), _gsi(2)],
    )
