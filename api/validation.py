"""Rules for a person's name, email and Saudi mobile (customers, owners, cashiers).

The SAME rules live in three places, kept identical on purpose:
- here (API: cashiers created by an owner),
- functions/pre_sign_up/handler.py (Cognito sign-up trigger; a Lambda asset can't import api/),
- web/src/lib/validation.ts (form warnings).
tests/unit/functions/test_pre_sign_up.py checks the API and Lambda copies give the same answers.
"""

import re

# Arabic letters + vowel marks (harakat) + tatweel; excludes Arabic-Indic digits (U+0660-0669, U+06F0-06F9)
# and Arabic punctuation (، ؛ ؟).
_ARABIC = "ء-ٰٟ-ۓ"
_ARABIC_LETTERS = "ء-غف-يٱ-ۓ"
# Emoji (pictographs, symbols, flags, skin tones) + zero-width joiner + emoji variation selector.
# Keycap emoji (1️⃣) are NOT included: they are digits.
_EMOJI = (
    "©®‼⁉™ℹ↔-↙↩↪⌚-⏿Ⓜ▪-◾"
    "☀-➿⤴⤵⬅-⭕〰〽㊗㊙\U0001f000-\U0001faff‍️"
)
_NAME_RE = re.compile(f"^[A-Za-z{_ARABIC}{_EMOJI} '’.\\-]+$")
_LETTER_RE = re.compile(f"[A-Za-z{_ARABIC_LETTERS}]")
NAME_MAX = 80

EMAIL_RE = re.compile(r"^[^@\s,;<>()\[\]]+@[^@\s,;<>()\[\]]+\.[A-Za-z]{2,}$")
SAUDI_MOBILE_RE = re.compile(r"^\+9665\d{8}$")  # E.164, as Cognito stores it

NAME_MESSAGE = "Name may only contain Arabic or English letters, spaces, - ' . and emoji (no numbers or symbols)"
PHONE_MESSAGE = "Phone must be a Saudi mobile number in the form +9665XXXXXXXX"
EMAIL_MESSAGE = "Enter a valid email address (name@domain.tld)"


def is_person_name(value: str) -> bool:
    v = (value or "").strip()
    return 0 < len(v) <= NAME_MAX and bool(_NAME_RE.match(v)) and bool(_LETTER_RE.search(v))


def is_email(value: str) -> bool:
    v = (value or "").strip()
    return len(v) <= 254 and bool(EMAIL_RE.match(v))


def is_saudi_mobile(value: str) -> bool:
    return bool(SAUDI_MOBILE_RE.match(value or ""))


def check_person_name(value: str) -> str:
    """Pydantic AfterValidator: returns the trimmed name or raises with a clear message."""
    if not is_person_name(value):
        raise ValueError(NAME_MESSAGE)
    return value.strip()


def check_saudi_mobile(value: str) -> str:
    if not is_saudi_mobile(value):
        raise ValueError(PHONE_MESSAGE)
    return value
