"""Post-confirmation trigger: put a self-registered user in their group.

One role per account: custom:signupRole = "owner" -> `owner`, anything else -> `customer`.
New customers' emails are also sent to SES for verification (sandbox), so the pickup email can reach them.
An owner who wants to order food signs up again as a customer with another email.
Cashiers never sign up themselves (an owner creates them through the API).

Runs ONLY for `PostConfirmation_ConfirmSignUp`, so a cashier (created by AdminCreateUser) who resets a
forgotten password (`PostConfirmation_ConfirmForgotPassword`) never gains groups, and editing signupRole
later does nothing. Never logs email, phone or other personal data.
"""

import logging
import os

import boto3
from botocore.exceptions import ClientError

SIGN_UP = "PostConfirmation_ConfirmSignUp"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_cognito = None
_ses = None


def _client():
    global _cognito
    if _cognito is None:
        _cognito = boto3.client("cognito-idp")
    return _cognito


def _ses_client():
    global _ses
    if _ses is None:
        _ses = boto3.client("sesv2")
    return _ses


def should_verify(groups: list[str], email: str | None) -> bool:
    """Only real customer addresses: owners/cashiers don't get pickup emails; @example.com is demo data."""
    return (
        os.environ.get("AUTO_VERIFY_EMAIL", "1") == "1"
        and "customer" in groups
        and bool(email)
        and not email.lower().endswith("@example.com")
    )


def request_email_verification(email: str) -> None:
    """SES sandbox: AWS emails the customer a link; after they click it, pickup emails can reach them.
    Never blocks sign-up: any problem is logged (without the address) and ignored."""
    try:
        _ses_client().create_email_identity(EmailIdentity=email)
        logger.info("requested SES verification for new customer")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code != "AlreadyExistsException":
            logger.warning("SES verification request failed: %s", code)


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
    if should_verify(groups, attributes.get("email")):
        request_email_verification(attributes["email"])
    return event
