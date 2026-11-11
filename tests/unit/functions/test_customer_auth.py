import pytest
from moto import mock_aws
from moto.core import DEFAULT_ACCOUNT_ID
from moto.sns import sns_backends

from .conftest import load_handler

PHONE = "+966500000000"


@pytest.fixture
def fn(monkeypatch):
    monkeypatch.setenv("OTP_MODE", "fixed")
    monkeypatch.setenv("FIXED_OTP", "1234")
    return load_handler("customer_auth")


def _event(source: str, **request) -> dict:
    return {"triggerSource": source, "request": request, "response": {}}


def _challenge(ok: bool, code: str = "1234") -> dict:
    return {"challengeName": "CUSTOM_CHALLENGE", "challengeResult": ok, "challengeMetadata": f"CODE-{code}"}


# --- PreSignUp ---------------------------------------------------------------


def test_pre_sign_up_auto_confirms_and_verifies_phone(fn):
    out = fn.handler(
        _event("PreSignUp_SignUp", userAttributes={"phone_number": PHONE, "name": "Sara"}), None
    )
    assert out["response"] == {"autoConfirmUser": True, "autoVerifyPhone": True}


# --- DefineAuthChallenge -----------------------------------------------------


def _define(fn, session):
    return fn.handler(_event("DefineAuthChallenge_Authentication", session=session), None)["response"]


def test_define_first_call_asks_for_code(fn):
    r = _define(fn, [])
    assert r == {"issueTokens": False, "failAuthentication": False, "challengeName": "CUSTOM_CHALLENGE"}


def test_define_correct_answer_issues_tokens(fn):
    assert _define(fn, [_challenge(True)])["issueTokens"] is True


def test_define_wrong_answer_retries(fn):
    assert _define(fn, [_challenge(False)])["challengeName"] == "CUSTOM_CHALLENGE"


def test_define_fails_after_three_wrong(fn):
    r = _define(fn, [_challenge(False)] * 3)
    assert r["failAuthentication"] is True and r["issueTokens"] is False


def test_define_rejects_non_custom_challenge(fn):
    r = _define(fn, [{"challengeName": "SRP_A", "challengeResult": True}])
    assert r["failAuthentication"] is True


# --- CreateAuthChallenge -----------------------------------------------------


def _create(fn, session=None):
    event = _event(
        "CreateAuthChallenge_Authentication",
        session=session or [],
        userAttributes={"phone_number": PHONE},
        challengeName="CUSTOM_CHALLENGE",
    )
    return fn.handler(event, None)["response"]


def test_create_fixed_mode_uses_1234(fn):
    r = _create(fn)
    assert r["privateChallengeParameters"] == {"answer": "1234"}
    assert r["publicChallengeParameters"] == {"delivery": "fixed"}
    assert "1234" not in str(r["publicChallengeParameters"])  # never leak the code to the client


def test_create_retry_keeps_same_code(fn, monkeypatch):
    monkeypatch.setenv("OTP_MODE", "sms")  # even in sms mode a retry must not send a new SMS
    r = _create(fn, session=[_challenge(False, code="987654")])
    assert r["privateChallengeParameters"] == {"answer": "987654"}


@mock_aws
def test_create_sms_mode_sends_random_code(fn, monkeypatch):
    monkeypatch.setenv("OTP_MODE", "sms")
    r = _create(fn)
    code = r["privateChallengeParameters"]["answer"]
    assert len(code) == 6 and code.isdigit()

    sent = sns_backends[DEFAULT_ACCOUNT_ID]["us-east-1"].sms_messages
    assert [(phone, msg) for phone, msg, *_ in sent.values()] == [(PHONE, f"Sumaat code: {code}")]


# --- VerifyAuthChallengeResponse ---------------------------------------------


@pytest.mark.parametrize(("answer", "ok"), [("1234", True), (" 1234 ", True), ("0000", False), ("", False)])
def test_verify(fn, answer, ok):
    event = _event(
        "VerifyAuthChallengeResponse_Authentication",
        privateChallengeParameters={"answer": "1234"},
        challengeAnswer=answer,
    )
    assert fn.handler(event, None)["response"]["answerCorrect"] is ok


def test_unknown_trigger_passes_through(fn):
    event = _event("PostAuthentication_Authentication")
    assert fn.handler(event, None) is event
