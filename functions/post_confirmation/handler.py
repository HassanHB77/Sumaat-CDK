"""Business pool post-confirmation trigger.

Adds a self-registered user to the `owner` group. Runs ONLY for
`PostConfirmation_ConfirmSignUp`, so a cashier (created by AdminCreateUser) who
confirms a forgotten password (`PostConfirmation_ConfirmForgotPassword`) never
becomes an owner. Never logs email or other personal data.
"""

import logging

import boto3

OWNER_GROUP = "owner"
SIGN_UP = "PostConfirmation_ConfirmSignUp"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_cognito = None


def _client():
    global _cognito
    if _cognito is None:
        _cognito = boto3.client("cognito-idp")
    return _cognito


def handler(event, _context):
    source = event.get("triggerSource")
    if source != SIGN_UP:
        logger.info("skip triggerSource=%s", source)
        return event

    _client().admin_add_user_to_group(
        UserPoolId=event["userPoolId"],
        Username=event["userName"],
        GroupName=OWNER_GROUP,
    )
    logger.info("added sub=%s to %s", event["request"]["userAttributes"].get("sub"), OWNER_GROUP)
    return event
