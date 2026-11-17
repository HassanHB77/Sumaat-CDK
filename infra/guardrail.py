"""Amazon Bedrock Guardrail for the Sumaat AI chat (Step 9). Settings chosen by the project owner (Nov 13).

Checks every customer message and every reply, in English AND Arabic (Standard tier):
  - content filters: STRICT (HIGH) for hate, insults, sexual, violence, misconduct + prompt attacks (input)
  - AWS managed profanity word list
  - denied topics: medical advice, politics & religion debates, financial & legal advice, other food apps
  - personal info: phone + email masked; card numbers, CVV, expiry and Saudi IBANs blocked
When it blocks, the "reply" is BLOCKED_MARKER: the agent turns that into a `blocked` event and the website shows
its own friendly message in the site language (agent/main.py, agent/text.py).
"""

import hashlib
import json

from aws_cdk import aws_bedrock as bedrock
from constructs import Construct

from agent.text import BLOCKED_MARKER

GUARDRAIL_PROFILE = "us.guardrail.v1:0"  # cross-region profile: required for the Standard (multilingual) tier

STRICT_FILTERS = ["HATE", "INSULTS", "SEXUAL", "VIOLENCE", "MISCONDUCT"]

# name: (definition, examples). Narrow on purpose, so normal food questions still pass.
DENIED_TOPICS = {
    "Medical-advice": (
        "Requests for medical or health advice: diagnosing conditions, treatments, medication, or what to eat "
        "for an illness such as diabetes or pregnancy. Dish calories and diet tags are not medical advice.",
        ["What should I eat for diabetes?", "Is this safe with my blood pressure medicine?",
         "ما الأكل المناسب لمريض السكري؟"],
    ),
    "Politics-and-religion-debates": (
        "Opinions, arguments or debates about politics, governments, elections or religious disputes. "
        "Practical food questions such as halal food or Ramadan hours are not included.",
        ["What do you think about the government?", "Which religion is right?", "ما رأيك في الانتخابات؟"],
    ),
    "Financial-and-legal-advice": (
        "Advice about investments, stocks, crypto, loans, taxes or legal matters and disputes.",
        ["Should I buy this stock?", "How do I sue a restaurant?", "هل أستثمر في العملات الرقمية؟"],
    ),
    "Other-food-apps": (
        "Naming, comparing or recommending other food ordering or delivery apps and companies instead of Sumaat. "
        "Questions about whether Sumaat delivers are not included.",
        ["Is HungerStation better than this app?", "Recommend a delivery app", "أيهم أفضل جاهز أو مرسول؟"],
    ),
}

PII_MASKED = ["EMAIL", "PHONE"]
PII_BLOCKED = ["CREDIT_DEBIT_CARD_NUMBER", "CREDIT_DEBIT_CARD_CVV", "CREDIT_DEBIT_CARD_EXPIRY"]
SAUDI_IBAN = r"\bSA\d{22}\b"


# The OWNER assistant answers questions about the owner's own sales. Bedrock's "financial advice" topic flags
# "how much did we sell / revenue" (checked live, 17 Nov), so the owner guardrail leaves that one topic out; the
# owner prompt refuses investment, tax and legal advice itself. Everything else is identical.
OWNER_DENIED_TOPICS = {k: v for k, v in DENIED_TOPICS.items() if k != "Financial-and-legal-advice"}


def settings_fingerprint(topics: dict | None = None) -> str:
    """Changes whenever a setting changes, so a new guardrail version gets published."""
    topics = DENIED_TOPICS if topics is None else topics
    data = [STRICT_FILTERS, topics, PII_MASKED, PII_BLOCKED, SAUDI_IBAN, BLOCKED_MARKER, GUARDRAIL_PROFILE]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def build_guardrail(
    scope: Construct,
    region: str,
    account: str,
    *,
    owner: bool = False,
) -> tuple[bedrock.CfnGuardrail, bedrock.CfnGuardrailVersion]:
    """The customer guardrail (default) or the owner guardrail (same settings minus the financial-advice topic)."""
    G = bedrock.CfnGuardrail
    topics = OWNER_DENIED_TOPICS if owner else DENIED_TOPICS
    prefix = "Owner" if owner else ""
    guardrail = G(
        scope,
        f"{prefix}Guardrail",
        name="sumaat-owner-chat" if owner else "sumaat-chat",
        description=(
            f"Sumaat AI chat ({'owners' if owner else 'customers'}): strict content filters, {len(topics)} denied "
            "topics, PII masking/blocking (EN + AR)"
        ),
        blocked_input_messaging=BLOCKED_MARKER,
        blocked_outputs_messaging=BLOCKED_MARKER,
        cross_region_config=G.GuardrailCrossRegionConfigProperty(
            guardrail_profile_arn=f"arn:aws:bedrock:{region}:{account}:guardrail-profile/{GUARDRAIL_PROFILE}"
        ),
        content_policy_config=G.ContentPolicyConfigProperty(
            filters_config=[
                *(G.ContentFilterConfigProperty(type=t, input_strength="HIGH", output_strength="HIGH") for t in STRICT_FILTERS),
                # Prompt attacks only apply to input (AWS requires NONE for output).
                G.ContentFilterConfigProperty(type="PROMPT_ATTACK", input_strength="HIGH", output_strength="NONE"),
            ],
            content_filters_tier_config=G.ContentFiltersTierConfigProperty(tier_name="STANDARD"),
        ),
        topic_policy_config=G.TopicPolicyConfigProperty(
            topics_config=[
                G.TopicConfigProperty(name=name, definition=definition, examples=examples, type="DENY")
                for name, (definition, examples) in topics.items()
            ],
            topics_tier_config=G.TopicsTierConfigProperty(tier_name="STANDARD"),
        ),
        word_policy_config=G.WordPolicyConfigProperty(
            managed_word_lists_config=[G.ManagedWordsConfigProperty(type="PROFANITY")]
        ),
        sensitive_information_policy_config=G.SensitiveInformationPolicyConfigProperty(
            pii_entities_config=[
                *(G.PiiEntityConfigProperty(type=t, action="ANONYMIZE") for t in PII_MASKED),
                *(G.PiiEntityConfigProperty(type=t, action="BLOCK") for t in PII_BLOCKED),
            ],
            regexes_config=[
                G.RegexConfigProperty(
                    name="saudi-iban", pattern=SAUDI_IBAN, action="BLOCK", description="Saudi IBAN (SA + 22 digits)"
                )
            ],
        ),
    )
    version = bedrock.CfnGuardrailVersion(
        scope,
        f"{prefix}GuardrailVersion",
        guardrail_identifier=guardrail.attr_guardrail_id,
        description=f"settings {settings_fingerprint(topics)}",  # new settings -> new description -> new version
    )
    return guardrail, version
