"""Cashier accounts, created and managed by the restaurant's owner.

A cashier is a Cognito user in the `cashier` group with custom:restaurantId = the restaurant, plus a
DynamoDB record RESTAURANT#<rid> / CASHIER#<sub> whose `status` (active | disabled) is checked on every
staff action (api/services/staff.py). No email is ever sent: the owner sets and shares the password.
Never logs email, phone or passwords.
"""

import logging

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from api import aws
from api.auth import Principal
from api.clock import now_iso
from api.errors import Conflict, Invalid, NotFound
from api.models import CashierCreate
from api.services.restaurants import load_owned
from api.services.staff import cashier_key
from api.settings import get_settings

logger = logging.getLogger(__name__)


def _pool() -> str:
    return get_settings().user_pool_id


def _cognito_error(e: ClientError):
    code = e.response["Error"]["Code"]
    if code == "UsernameExistsException":
        return Conflict("An account with this email already exists")
    if code in ("InvalidPasswordException", "InvalidParameterException"):
        return Invalid(e.response["Error"].get("Message", "Invalid value"))
    return None


def create(owner: Principal, rid: str, data: CashierCreate) -> dict:
    load_owned(owner, rid)
    cognito = aws.cognito()
    try:
        user = cognito.admin_create_user(
            UserPoolId=_pool(),
            Username=data.email,
            MessageAction="SUPPRESS",  # no invitation email
            UserAttributes=[
                {"Name": "email", "Value": data.email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "name", "Value": data.name},
                {"Name": "phone_number", "Value": data.phone},
                {"Name": "custom:restaurantId", "Value": rid},
            ],
        )["User"]
    except ClientError as e:
        raise (_cognito_error(e) or e) from e

    username = user["Username"]
    sub = next(a["Value"] for a in user["Attributes"] if a["Name"] == "sub")
    try:
        cognito.admin_set_user_password(UserPoolId=_pool(), Username=username, Password=data.password, Permanent=True)
        cognito.admin_add_user_to_group(UserPoolId=_pool(), Username=username, GroupName="cashier")
        ts = now_iso()
        record = {
            **cashier_key(rid, sub),
            "type": "CASHIER",
            "sub": sub,
            "username": username,
            "restaurantId": rid,
            "name": data.name,
            "email": data.email,
            "phone": data.phone,
            "status": "active",
            "createdAt": ts,
            "updatedAt": ts,
        }
        aws.table().put_item(Item=record)
    except Exception as e:
        # Don't leave a half-made login behind.
        logger.warning("Cashier setup failed for restaurant %s, removing the new user", rid)
        cognito.admin_delete_user(UserPoolId=_pool(), Username=username)
        if isinstance(e, ClientError) and (mapped := _cognito_error(e)):
            raise mapped from e
        raise
    return record


def list_for(owner: Principal, rid: str) -> list[dict]:
    load_owned(owner, rid)
    items = aws.table().query(
        KeyConditionExpression=Key("PK").eq(f"RESTAURANT#{rid}") & Key("SK").begins_with("CASHIER#")
    )["Items"]
    return sorted(items, key=lambda c: c["name"].lower())


def _load(owner: Principal, rid: str, sub: str) -> dict:
    load_owned(owner, rid)
    record = aws.table().get_item(Key=cashier_key(rid, sub)).get("Item")
    if record is None:
        raise NotFound("Cashier not found")
    return record


def _set_status(rid: str, sub: str, status: str) -> dict:
    return aws.table().update_item(
        Key=cashier_key(rid, sub),
        UpdateExpression="SET #s = :s, updatedAt = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status, ":t": now_iso()},
        ReturnValues="ALL_NEW",
    )["Attributes"]


def disable(owner: Principal, rid: str, sub: str) -> dict:
    record = _load(owner, rid, sub)
    # Record first: the API stops accepting this cashier immediately, even if Cognito is slow.
    updated = _set_status(rid, sub, "disabled")
    cognito = aws.cognito()
    cognito.admin_disable_user(UserPoolId=_pool(), Username=record["username"])
    cognito.admin_user_global_sign_out(UserPoolId=_pool(), Username=record["username"])
    return updated


def enable(owner: Principal, rid: str, sub: str) -> dict:
    record = _load(owner, rid, sub)
    aws.cognito().admin_enable_user(UserPoolId=_pool(), Username=record["username"])
    return _set_status(rid, sub, "active")


def reset_password(owner: Principal, rid: str, sub: str, password: str) -> None:
    record = _load(owner, rid, sub)
    cognito = aws.cognito()
    try:
        cognito.admin_set_user_password(UserPoolId=_pool(), Username=record["username"], Password=password, Permanent=True)
    except ClientError as e:
        raise (_cognito_error(e) or e) from e
    cognito.admin_user_global_sign_out(UserPoolId=_pool(), Username=record["username"])  # old sessions end
