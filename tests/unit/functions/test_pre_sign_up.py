import pytest

from api import validation as api_rules

from .conftest import load_handler

fn = load_handler("pre_sign_up")

GOOD_NAMES = [
    "Sara",
    "Sara Al-Ahmad",
    "O'Brien",
    "O’Brien",  # iPhone curly apostrophe
    "Abdullah Jr.",
    "سارة",
    "مُحَمَّد الحَسَاوي",  # with harakat
    "سارة 🌸",
    "Omar 👨‍🍳",  # emoji with zero-width joiner
    "Reem ❤️",  # emoji with variation selector
    "  Sara  ",  # trimmed
    "a" * 80,
]
BAD_NAMES = [
    "",
    "   ",
    "Sara2",
    "سارة٣",  # Arabic-Indic digit
    "سارة۳",  # Persian digit
    "a@b",
    "Sara_Q",
    "!!",
    "Sara!",
    "Sara #1",
    "🌸",  # no letter at all
    "-.'",
    "Omar 1️⃣",  # keycap emoji = a digit
    "سارة؟",  # Arabic question mark
    "<script>",
    "a" * 81,
]
GOOD_EMAILS = ["a@b.co", "sara.q+test@gmail.com", " owner.nakhla@example.com "]
BAD_EMAILS = ["", "sara@", "sara@gmail", "a b@c.com", "a@b.com,", "a@@b.com", "@b.com"]
GOOD_PHONES = ["+966500000001", "+966512345678"]
BAD_PHONES = ["", "+9665016283339999", "+96650162833", "+966412345678", "+96613123456", "966500000001",
              "0500000001", "+14155550100", "+96650000000a"]


@pytest.mark.parametrize("name", GOOD_NAMES)
def test_good_names(name):
    assert fn.is_person_name(name) and api_rules.is_person_name(name)


@pytest.mark.parametrize("name", BAD_NAMES)
def test_bad_names(name):
    assert not fn.is_person_name(name) and not api_rules.is_person_name(name)


@pytest.mark.parametrize("email", GOOD_EMAILS)
def test_good_emails(email):
    assert fn.is_email(email) and api_rules.is_email(email)


@pytest.mark.parametrize("email", BAD_EMAILS)
def test_bad_emails(email):
    assert not fn.is_email(email) and not api_rules.is_email(email)


@pytest.mark.parametrize("phone", GOOD_PHONES)
def test_good_phones(phone):
    assert fn.is_saudi_mobile(phone) and api_rules.is_saudi_mobile(phone)


@pytest.mark.parametrize("phone", BAD_PHONES)
def test_bad_phones(phone):
    assert not fn.is_saudi_mobile(phone) and not api_rules.is_saudi_mobile(phone)


def test_rules_are_identical_copies():
    """The Lambda can't import api/, so it carries a copy. Same patterns -> same answers."""
    for attr in ("_ARABIC", "_ARABIC_LETTERS", "_EMOJI", "NAME_MAX"):
        assert getattr(fn, attr) == getattr(api_rules, attr), attr
    for attr in ("_NAME_RE", "_LETTER_RE", "EMAIL_RE", "SAUDI_MOBILE_RE"):
        assert getattr(fn, attr).pattern == getattr(api_rules, attr).pattern, attr


def _event(**attrs) -> dict:
    base = {"name": "Sara Al-Ahmad", "email": "sara@example.com", "phone_number": "+966500000001"}
    return {
        "triggerSource": "PreSignUp_SignUp",
        "request": {"userAttributes": {**base, **attrs}},
        "response": {"autoConfirmUser": False, "autoVerifyEmail": False, "autoVerifyPhone": False},
    }


def test_valid_signup_passes_unchanged():
    event = _event()
    assert fn.handler(event, None) == event


@pytest.mark.parametrize(
    ("attrs", "code"),
    [
        ({"name": "Sara2"}, "invalid_name"),
        ({"email": "sara@"}, "invalid_email"),
        ({"phone_number": "+9665016283339999"}, "invalid_phone"),
        ({"phone_number": "+14155550100"}, "invalid_phone"),
    ],
)
def test_bad_attribute_is_refused_with_code(attrs, code):
    with pytest.raises(fn.InvalidAttribute, match=f"^{code}$"):
        fn.handler(_event(**attrs), None)


def test_missing_attributes_are_refused():
    with pytest.raises(fn.InvalidAttribute, match="^invalid_name$"):
        fn.handler({"triggerSource": "PreSignUp_AdminCreateUser", "request": {"userAttributes": {}}}, None)


def test_never_logs_personal_data(caplog):
    with caplog.at_level("INFO"), pytest.raises(fn.InvalidAttribute):
        fn.handler(_event(name="Sara2", email="secret.person@example.com"), None)
    assert "Sara2" not in caplog.text and "secret.person" not in caplog.text
