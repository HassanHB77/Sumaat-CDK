"""Post-confirmation trigger: put a self-registered user in their group.

One role per account: custom:signupRole = "owner" -> `owner`, anything else -> `customer`.
An owner who wants to order food signs up again as a customer with another email.
Cashiers never sign up themselves (an owner creates them through the API).

Runs ONLY for `PostConfirmation_ConfirmSignUp`, so a cashier (created by AdminCreateUser) who resets a
forgotten password (`PostConfirmation_ConfirmForgotPassword`) never gains groups, and editing signupRole
later does nothing. Never logs email, phone or other personal data.
"""

import logging

import boto3

SIGN_UP = "PostConfirmation_ConfirmSignUp"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_cognito = None


def _client():
    global _cognito
    if _cognito is None:
        _cognito = boto3.client("cognito-idp")
    return _cognito


def groups_for(attributes: dict) -> list[str]:
    return ["owner"] if attributes.get("custom:signupRole") == "owner" else ["customer"]


def handler(event, _context):
    source = event.get("triggerSource")
    if source != SIGN_UP:
        logger.info("skip triggerSource=%s", source)
        return event

    attributes = event["request"]["userAttributes"]
    groups = groups_for(attributes)
    for group in groups:
        _client().admin_add_user_to_group(
            UserPoolId=event["userPoolId"],
            Username=event["userName"],
            GroupName=group,
        )
    logger.info("added sub=%s to %s", attributes.get("sub"), ",".join(groups))
    return event
