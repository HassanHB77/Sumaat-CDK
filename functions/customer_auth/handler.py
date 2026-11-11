"""Customer pool: phone + OTP sign-in via Cognito custom-auth triggers.

One Lambda handles four triggers, chosen by `triggerSource`:
  PreSignUp_SignUp                    auto-confirm + mark phone verified (every login proves the phone)
  DefineAuthChallenge_Authentication  decide: issue tokens / ask again / fail
  CreateAuthChallenge_Authentication  make the code (fixed or random + SMS)
  VerifyAuthChallengeResponse_Authentication  compare the answer

OTP_MODE:
  fixed  -> code is FIXED_OTP (default "1234"), nothing is sent. DEMO ONLY:
            anyone can sign in as any phone number.
  sms    -> random 6-digit code sent with SNS.

Never logs the phone number or the code.
"""

import hmac
import logging
import os
import secrets

import boto3

MAX_ATTEMPTS = 3
CHALLENGE = "CUSTOM_CHALLENGE"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_sns = None


def _sns_client():
    global _sns
    if _sns is None:
        _sns = boto3.client("sns")
    return _sns


def _mode() -> str:
    return os.environ.get("OTP_MODE", "fixed")


# --- triggers ---------------------------------------------------------------


def pre_sign_up(event):
    event["response"]["autoConfirmUser"] = True
    if "phone_number" in event["request"].get("userAttributes", {}):
        event["response"]["autoVerifyPhone"] = True
    return event


def define_auth_challenge(event):
    session = event["request"].get("session") or []
    resp = event["response"]

    if session and session[-1].get("challengeName") == CHALLENGE and session[-1].get("challengeResult"):
        resp.update(issueTokens=True, failAuthentication=False)
    elif len(session) >= MAX_ATTEMPTS or any(s.get("challengeName") != CHALLENGE for s in session):
        resp.update(issueTokens=False, failAuthentication=True)
    else:
        resp.update(issueTokens=False, failAuthentication=False, challengeName=CHALLENGE)
    return event


def create_auth_challenge(event):
    session = event["request"].get("session") or []
    previous = session[-1].get("challengeMetadata", "") if session else ""

    if previous.startswith("CODE-"):
        code = previous.removeprefix("CODE-")  # retry: keep the same code, don't resend
    elif _mode() == "sms":
        code = f"{secrets.randbelow(1_000_000):06d}"
        _sns_client().publish(
            PhoneNumber=event["request"]["userAttributes"]["phone_number"],
            Message=f"Sumaat code: {code}",
            MessageAttributes={
                "AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"}
            },
        )
        logger.info("otp sent mode=sms")
    else:
        code = os.environ.get("FIXED_OTP", "1234")
        logger.info("otp mode=fixed")

    resp = event["response"]
    resp["publicChallengeParameters"] = {"delivery": _mode()}
    resp["privateChallengeParameters"] = {"answer": code}
    resp["challengeMetadata"] = f"CODE-{code}"
    return event


def verify_auth_challenge_response(event):
    expected = event["request"]["privateChallengeParameters"].get("answer", "")
    given = str(event["request"].get("challengeAnswer", "")).strip()
    event["response"]["answerCorrect"] = bool(expected) and hmac.compare_digest(expected, given)
    return event


_HANDLERS = {
    "PreSignUp_SignUp": pre_sign_up,
    "DefineAuthChallenge_Authentication": define_auth_challenge,
    "CreateAuthChallenge_Authentication": create_auth_challenge,
    "VerifyAuthChallengeResponse_Authentication": verify_auth_challenge_response,
}


def handler(event, _context):
    source = event.get("triggerSource")
    fn = _HANDLERS.get(source)
    if fn is None:
        logger.warning("unhandled triggerSource=%s", source)
        return event
    return fn(event)
