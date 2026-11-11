import boto3
import pytest
from boto3.dynamodb.conditions import Key
from moto import mock_aws

from scripts.seed import seed, stable_id
from scripts.seed_data import CATEGORIES, RESTAURANTS
from tests.ddb import create_table

PASSWORD = "Test#Pass2026"


@pytest.fixture
def env():
    with mock_aws():
        table = create_table(boto3.resource("dynamodb", region_name="us-east-1"))
        cognito = boto3.client("cognito-idp", region_name="us-east-1")
        pool_id = cognito.create_user_pool(
            PoolName="sumaat-users",
            UsernameAttributes=["email"],
            Schema=[
                {"Name": "restaurantId", "AttributeDataType": "String", "Mutable": True},
                {"Name": "signupRole", "AttributeDataType": "String", "Mutable": True},
            ],
        )["UserPool"]["Id"]
        for group in ("customer", "owner", "cashier"):
            cognito.create_group(UserPoolId=pool_id, GroupName=group)
        yield table, cognito, pool_id


def test_seed_writes_everything(env):
    table, cognito, pool_id = env
    summary = seed(table, cognito, pool_id, PASSWORD)
    n_items = sum(len(r["items"]) for r in RESTAURANTS)
    assert summary["restaurants"] == 3
    assert summary["items"] == n_items
    # profiles + items + owner locks + CONFIG/CATEGORIES (daily order counters are created by the API)
    assert table.scan(Select="COUNT")["Count"] == 3 + n_items + 3 + 1


def test_restaurant_page_is_one_query(env):
    table, *_ = env
    seed(table)
    rid = stable_id("restaurant", "nakhla-kitchen")
    items = table.query(KeyConditionExpression=Key("PK").eq(f"RESTAURANT#{rid}"))["Items"]
    assert {i["SK"].split("#")[0] for i in items} == {"PROFILE", "ITEM"}


def test_geo_lookup_finds_restaurants(env):
    table, *_ = env
    seed(table)
    profile = table.get_item(Key={"PK": f"RESTAURANT#{stable_id('restaurant', 'nakhla-kitchen')}", "SK": "PROFILE"})["Item"]
    hits = table.query(IndexName="GSI1", KeyConditionExpression=Key("GSI1PK").eq(profile["GSI1PK"]))["Items"]
    assert profile["id"] in {h["id"] for h in hits}


def test_money_is_int_halalas(env):
    table, *_ = env
    seed(table)
    items = [i for i in table.scan()["Items"] if i["type"] == "MENU_ITEM"]
    assert all(int(i["priceHalalas"]) == i["priceHalalas"] and i["priceHalalas"] > 0 for i in items)


def test_owner_linked_both_ways(env):
    table, cognito, pool_id = env
    seed(table, cognito, pool_id, PASSWORD)
    rid = stable_id("restaurant", "qaisariya-grill")
    user = cognito.admin_get_user(UserPoolId=pool_id, Username="owner.qaisariya@example.com")
    attrs = {a["Name"]: a["Value"] for a in user["UserAttributes"]}
    assert attrs["custom:restaurantId"] == rid
    assert attrs["name"] == "Khalid Al-Qaisi"
    groups = cognito.admin_list_groups_for_user(UserPoolId=pool_id, Username="owner.qaisariya@example.com")
    assert [g["GroupName"] for g in groups["Groups"]] == ["owner"]
    assert attrs["phone_number"] == "+966500000102"
    lock = table.get_item(Key={"PK": f"OWNER#{attrs['sub']}", "SK": "RESTAURANT"})["Item"]
    assert lock["restaurantId"] == rid
    profile = table.get_item(Key={"PK": f"RESTAURANT#{rid}", "SK": "PROFILE"})["Item"]
    assert profile["ownerSub"] == attrs["sub"]


def test_rerun_is_idempotent_and_keeps_daily_counters(env):
    table, cognito, pool_id = env
    seed(table, cognito, pool_id, PASSWORD)
    rid = stable_id("restaurant", "mubarraz-dates-coffee")
    key = {"PK": f"RESTAURANT#{rid}", "SK": "COUNTER#2026-11-12"}
    table.update_item(Key=key, UpdateExpression="ADD seq :n", ExpressionAttributeValues={":n": 5})  # 5 real orders
    before = table.scan(Select="COUNT")["Count"]
    seed(table, cognito, pool_id, PASSWORD)
    assert table.scan(Select="COUNT")["Count"] == before
    assert table.get_item(Key=key)["Item"]["seq"] == 5  # the seed never touches order numbers
    assert len(cognito.list_users(UserPoolId=pool_id)["Users"]) == 3


def test_categories_cover_seed_data_and_survive_rerun(env):
    table, *_ = env
    seed(table)
    used = {i["category"] for r in RESTAURANTS for i in r["items"]}
    assert used <= set(CATEGORIES)  # every seeded item has a valid category

    key = {"PK": "CONFIG", "SK": "CATEGORIES"}
    table.update_item(  # what the CLI command does
        Key=key, UpdateExpression="ADD categories :c", ExpressionAttributeValues={":c": {"Soups"}}
    )
    seed(table)
    assert table.get_item(Key=key)["Item"]["categories"] == set(CATEGORIES) | {"Soups"}


def test_rerun_removes_old_customer_group_from_owners(env):
    table, cognito, pool_id = env
    seed(table, cognito, pool_id, PASSWORD)
    email = "owner.nakhla@example.com"
    cognito.admin_add_user_to_group(UserPoolId=pool_id, Username=email, GroupName="customer")  # old two-role design
    seed(table, cognito, pool_id, PASSWORD)
    groups = cognito.admin_list_groups_for_user(UserPoolId=pool_id, Username=email)["Groups"]
    assert [g["GroupName"] for g in groups] == ["owner"]
