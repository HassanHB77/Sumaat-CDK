"""Pre sign-up trigger: refuse accounts with a bad name, email or phone.

Runs for every new account: self sign-up in the browser (customer/owner) AND AdminCreateUser (cashiers from the
API, seed script). Sign-up goes straight from the browser to Cognito, so this is the server-side guard for
anyone who skips the website.

Raising makes Cognito refuse the account with UserLambdaValidationException:
"PreSignUp failed with error invalid_name." The web app maps the code (invalid_name / invalid_email /
invalid_phone) to a translated message.

Rules are a copy of api/validation.py (a Lambda asset can't import api/); a test keeps the two identical.
Never logs the values themselves (personal data), only which field failed.
"""

import logging
import re

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- same rules as api/validation.py -------------------------------------------------------------------------
_ARABIC = "ء-ٰٟ-ۓ"
_ARABIC_LETTERS = "ء-غف-يٱ-ۓ"
_EMOJI = (
    "©®‼⁉™ℹ↔-↙↩↪⌚-⏿Ⓜ▪-◾"
    "☀-➿⤴⤵⬅-⭕〰〽㊗㊙\U0001f000-\U0001faff‍️"
)
_NAME_RE = re.compile(f"^[A-Za-z{_ARABIC}{_EMOJI} '’.\\-]+$")
_LETTER_RE = re.compile(f"[A-Za-z{_ARABIC_LETTERS}]")
NAME_MAX = 80
EMAIL_RE = re.compile(r"^[^@\s,;<>()\[\]]+@[^@\s,;<>()\[\]]+\.[A-Za-z]{2,}$")
SAUDI_MOBILE_RE = re.compile(r"^\+9665\d{8}$")


def is_person_name(value: str) -> bool:
    v = (value or "").strip()
    return 0 < len(v) <= NAME_MAX and bool(_NAME_RE.match(v)) and bool(_LETTER_RE.search(v))


def is_email(value: str) -> bool:
    v = (value or "").strip()
    return len(v) <= 254 and bool(EMAIL_RE.match(v))


def is_saudi_mobile(value: str) -> bool:
    return bool(SAUDI_MOBILE_RE.match(value or ""))


# -------------------------------------------------------------------------------------------------------------


class InvalidAttribute(Exception):
    """Message is the code the web app maps to a translated warning."""


def handler(event, _context):
    attrs = (event.get("request") or {}).get("userAttributes") or {}
    for code, ok in (
        ("invalid_name", is_person_name(attrs.get("name", ""))),
        ("invalid_email", is_email(attrs.get("email", ""))),
        ("invalid_phone", is_saudi_mobile(attrs.get("phone_number", ""))),
    ):
        if not ok:
            logger.info("Sign-up refused: %s (%s)", code, event.get("triggerSource"))
            raise InvalidAttribute(code)
    return event
