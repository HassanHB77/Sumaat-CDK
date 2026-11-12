import logging

import boto3
import pytest
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError
from moto import mock_aws

from tests.ddb import create_table

from .conftest import load_handler

_ser = TypeSerializer()

ORDER = {
    "PK": "ORDER#o1",
    "SK": "ORDER",
    "type": "ORDER",
    "id": "o1",
    "orderNumber": 7,
    "businessDate": "2026-11-12",
    "restaurantName": "Nakhla Kitchen",
    "restaurantNameAr": "مطبخ النخلة",
    "customerName": "Sara Al-Qahtani",
    "customerEmail": "sara.real@example.org",
    "items": [{"itemId": "i1", "name": "Harees", "nameAr": "هريس", "qty": 2, "unitPriceHalalas": 2200, "lineTotalHalalas": 4400}],
    "totalHalalas": 4400,
    "status": "READY_FOR_PICKUP",
}


def record(old_status="ACCEPTED", new=None, seq="1"):
    new = new or ORDER
    old = {**new, "status": old_status}
    img = lambda d: {k: _ser.serialize(v) for k, v in d.items()}  # noqa: E731
    return {"eventName": "MODIFY", "dynamodb": {"SequenceNumber": seq, "OldImage": img(old), "NewImage": img(new)}}


class FakeSes:
    def __init__(self, error=None):
        self.sent = []
        self.error = error

    def send_email(self, **kw):
        if self.error:
            raise ClientError({"Error": self.error}, "SendEmail")
        self.sent.append(kw)
        return {"MessageId": "m1"}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "sumaat")
    monkeypatch.setenv("SITE_URL", "https://site.example")
    monkeypatch.setenv("NOTIFY_MODE", "email")
    with mock_aws():
        table = create_table(boto3.resource("dynamodb", region_name="us-east-1"))
        table.put_item(Item=ORDER)
        fn = load_handler("notify")
        fn._sender = "sender@example.org"
        ses = FakeSes()
        fn._clients["ses"] = ses
        yield fn, table, ses


def test_sends_once_with_subject_link_and_both_languages(env):
    fn, table, ses = env
    assert fn.handler({"Records": [record()]}, None) == {"batchItemFailures": []}
    (mail,) = ses.sent
    assert mail["Destination"] == {"ToAddresses": ["sara.real@example.org"]}
    assert mail["FromEmailAddress"] == "Sumaat <sender@example.org>"
    simple = mail["Content"]["Simple"]
    assert simple["Subject"]["Data"].startswith("Order #7 is ready for pickup — Nakhla Kitchen")
    body = simple["Body"]["Html"]["Data"]
    assert "https://site.example/orders/o1" in body
    assert "مطبخ النخلة" in body and "هريس" in body and "44.00" in body
    assert "Thu 12 Nov" in simple["Body"]["Text"]["Data"]
    assert "pickupEmailAt" in table.get_item(Key={"PK": "ORDER#o1", "SK": "ORDER"})["Item"]


def test_duplicate_event_sends_nothing_more(env):
    fn, _, ses = env
    fn.handler({"Records": [record(seq="1")]}, None)
    fn.handler({"Records": [record(seq="2")]}, None)  # retried/duplicated delivery
    assert len(ses.sent) == 1


@pytest.mark.parametrize("old_status", ["PLACED", "READY_FOR_PICKUP"])
def test_only_accepted_to_ready(env, old_status):
    fn, _, ses = env
    assert fn.process(record(old_status=old_status)) == "skipped-not-ready"
    assert ses.sent == []


def test_not_verified_in_sandbox_is_skipped_not_retried(env):
    fn, table, _ = env
    fn._clients["ses"] = FakeSes(
        error={"Code": "MessageRejected", "Message": "Email address is not verified. The following identities failed"}
    )
    assert fn.handler({"Records": [record()]}, None) == {"batchItemFailures": []}
    assert fn.process(record()) == "skipped-duplicate"  # mark kept: no endless retries


def test_other_ses_error_unmarks_and_reports_failure(env):
    fn, table, _ = env
    fn._clients["ses"] = FakeSes(error={"Code": "Throttling", "Message": "slow down"})
    assert fn.handler({"Records": [record(seq="9")]}, None) == {"batchItemFailures": [{"itemIdentifier": "9"}]}
    assert "pickupEmailAt" not in table.get_item(Key={"PK": "ORDER#o1", "SK": "ORDER"})["Item"]
    ok = FakeSes()
    fn._clients["ses"] = ok
    assert fn.process(record()) == "sent"  # the retry succeeds


def test_log_mode_sends_nothing(env, monkeypatch):
    fn, _, ses = env
    monkeypatch.setenv("NOTIFY_MODE", "log")
    assert fn.process(record()) == "logged"
    assert ses.sent == []


def test_no_email_skipped(env):
    fn, _, ses = env
    assert fn.process(record(new={**ORDER, "customerEmail": None})) == "skipped-no-email"
    assert ses.sent == []


def test_logs_have_no_personal_data(env, caplog):
    fn, _, _ = env
    with caplog.at_level(logging.INFO):
        fn.handler({"Records": [record()]}, None)
    text = caplog.text
    assert "o1" in text
    for private in ("sara.real@example.org", "Sara", "sender@example.org"):
        assert private not in text
