"""Pickup email: DynamoDB stream -> (only orders that just became READY_FOR_PICKUP) -> Amazon SES.

The event source filter in infra/notify_stack.py already limits events to ORDER items whose status changed
ACCEPTED -> READY_FOR_PICKUP; the same check is repeated here (defence in depth).

Exactly once: before sending, the order gets `pickupEmailAt` with a conditional write. A retried/duplicate event
finds the mark and skips. If SES fails, the mark is removed and the record is reported as failed so it is retried.
SES sandbox: an address that hasn't been verified yet is skipped (logged by order id), not retried.

NOTIFY_MODE: email (default) | log (no SES call, just "would email order X").
Never logs email addresses or names: only order ids and outcomes.
"""

import html
import logging
import os
from datetime import UTC, date, datetime

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_deserializer = TypeDeserializer()
_clients: dict = {}
_sender: str | None = None


def _ses():
    if "ses" not in _clients:
        _clients["ses"] = boto3.client("sesv2")
    return _clients["ses"]


def _table():
    if "table" not in _clients:
        _clients["table"] = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    return _clients["table"]


def _sender_address() -> str:
    """Kept in SSM Parameter Store so the address isn't in the code or the repo."""
    global _sender
    if _sender is None:
        name = os.environ.get("SENDER_PARAM", "/sumaat/notify/sender")
        _sender = boto3.client("ssm").get_parameter(Name=name)["Parameter"]["Value"]
    return _sender


def _image(raw: dict | None) -> dict:
    return {k: _deserializer.deserialize(v) for k, v in (raw or {}).items()}


def is_ready_transition(old: dict, new: dict) -> bool:
    return new.get("type") == "ORDER" and old.get("status") == "ACCEPTED" and new.get("status") == "READY_FOR_PICKUP"


# --- the email --------------------------------------------------------------------------------

AR_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def _sar(halalas) -> str:
    return f"{int(halalas) / 100:.2f}"


def build_email(order: dict, site_url: str) -> tuple[str, str, str]:
    """(subject, text, html), English then Arabic. Western digits in both."""
    n = int(order["orderNumber"])
    d = date.fromisoformat(order["businessDate"])
    en_date = d.strftime("%a %d %b").replace(" 0", " ")
    ar_date = f"{AR_DAYS[d.weekday()]} {d.day} {AR_MONTHS[d.month - 1]}"
    name_en = order.get("restaurantName") or ""
    name_ar = order.get("restaurantNameAr") or name_en
    total = _sar(order.get("totalHalalas", 0))
    link = f"{site_url.rstrip('/')}/orders/{order['id']}" if site_url else ""
    items = order.get("items") or []

    subject = f"Order #{n} is ready for pickup — {name_en} · طلبك #{n} جاهز للاستلام"

    lines_en = [f"  {int(i['qty'])} × {i.get('name', '')}" for i in items]
    lines_ar = [f"  {int(i['qty'])} × {i.get('nameAr') or i.get('name', '')}" for i in items]
    text = "\n".join(
        [
            f"Your order #{n} ({en_date}) at {name_en} is ready for pickup.",
            *lines_en,
            f"Total: {total} SAR (VAT included). Show #{n} at the counter and pay there.",
            link,
            "",
            f"طلبك رقم #{n} ({ar_date}) من {name_ar} جاهز للاستلام.",
            *lines_ar,
            f"الإجمالي: {total} ر.س (شامل الضريبة). أظهر الرقم #{n} عند الكاشير وادفع هناك.",
        ]
    )

    e = html.escape
    li_en = "".join(f"<li>{int(i['qty'])} × {e(i.get('name', ''))}</li>" for i in items)
    li_ar = "".join(f"<li>{int(i['qty'])} × {e(i.get('nameAr') or i.get('name', ''))}</li>" for i in items)
    button = (
        f'<p><a href="{e(link)}" style="background:#FF5722;color:#fff;padding:10px 18px;border-radius:10px;'
        f'text-decoration:none;font-weight:bold">View order · عرض الطلب</a></p>'
        if link
        else ""
    )
    body = f"""<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;color:#111">
<h2 style="margin:0 0 4px">Order #{n} is ready! 🎉</h2>
<p style="color:#6c757d;margin:0 0 12px">{e(name_en)} · {e(en_date)}</p>
<ul>{li_en}</ul>
<p><b>Total: {total} SAR</b> (VAT included)<br>Show <b>#{n}</b> at the counter and pay there.</p>
{button}
<hr style="border:none;border-top:1px solid #e9ecef;margin:20px 0">
<div dir="rtl" lang="ar" style="text-align:right">
<h2 style="margin:0 0 4px">طلبك رقم #{n} جاهز! 🎉</h2>
<p style="color:#6c757d;margin:0 0 12px">{e(name_ar)} · {e(ar_date)}</p>
<ul>{li_ar}</ul>
<p><b>الإجمالي: {total} ر.س</b> (شامل الضريبة)<br>أظهر الرقم <b>#{n}</b> عند الكاشير وادفع هناك.</p>
</div>
</div>"""
    return subject, text, body


# --- processing -------------------------------------------------------------------------------


def _mark(order_id: str) -> bool:
    """True if we are the first to handle this order's pickup email."""
    try:
        _table().update_item(
            Key={"PK": f"ORDER#{order_id}", "SK": "ORDER"},
            UpdateExpression="SET pickupEmailAt = :t",
            ConditionExpression="attribute_exists(PK) AND attribute_not_exists(pickupEmailAt)",
            ExpressionAttributeValues={":t": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def _unmark(order_id: str) -> None:
    _table().update_item(Key={"PK": f"ORDER#{order_id}", "SK": "ORDER"}, UpdateExpression="REMOVE pickupEmailAt")


def process(record: dict) -> str:
    """Returns the outcome (for logs/tests): sent, skipped-*, logged, not-verified."""
    ddb = record.get("dynamodb", {})
    old, new = _image(ddb.get("OldImage")), _image(ddb.get("NewImage"))
    if not is_ready_transition(old, new):
        return "skipped-not-ready"
    order_id = new["id"]
    to = new.get("customerEmail")
    if not to:
        logger.info("order %s: no customer email, skipped", order_id)
        return "skipped-no-email"
    if os.environ.get("NOTIFY_MODE", "email") == "log":
        logger.info("order %s: would send pickup email (NOTIFY_MODE=log)", order_id)
        return "logged"
    if not _mark(order_id):
        logger.info("order %s: pickup email already handled, skipped", order_id)
        return "skipped-duplicate"

    subject, text, body = build_email(new, os.environ.get("SITE_URL", ""))
    try:
        _ses().send_email(
            FromEmailAddress=f"Sumaat <{_sender_address()}>",
            Destination={"ToAddresses": [to]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": text, "Charset": "UTF-8"}, "Html": {"Data": body, "Charset": "UTF-8"}},
                }
            },
        )
    except ClientError as e:
        err = e.response["Error"]
        if err["Code"] == "MessageRejected" and "not verified" in err.get("Message", ""):
            # SES sandbox: the customer hasn't clicked the AWS verification link yet. Keep the mark, don't retry.
            logger.info("order %s: recipient not verified in SES yet, skipped", order_id)
            return "not-verified"
        _unmark(order_id)  # let the retry send it
        raise
    logger.info("order %s: pickup email sent", order_id)
    return "sent"


def handler(event, _context):
    failures = []
    for record in event.get("Records", []):
        try:
            process(record)
        except Exception:
            seq = record.get("dynamodb", {}).get("SequenceNumber")
            logger.exception("pickup email failed for record %s", seq)
            failures.append({"itemIdentifier": seq})
    return {"batchItemFailures": failures}  # only failed records are retried
