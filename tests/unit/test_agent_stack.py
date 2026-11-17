import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Annotations, Match, Template

from infra.agent_stack import RUNTIME_NAME, AgentStack
from infra.auth_stack import AuthStack
from infra.common import apply_project_guards
from infra.data_stack import DataStack

ENV = cdk.Environment(account="123456789012", region="us-east-1")


@pytest.fixture(scope="module")
def stack() -> AgentStack:
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})
    data = DataStack(app, "SumaatData", env=ENV)
    auth = AuthStack(app, "SumaatAuth", env=ENV)
    agent = AgentStack(
        app, "SumaatAgent", table=data.table, user_pool=auth.user_pool, user_pool_client=auth.client, env=ENV
    )
    apply_project_guards(app)
    app.synth()
    return agent


@pytest.fixture(scope="module")
def template(stack) -> Template:
    return Template.from_stack(stack)


def _runtime(template) -> dict:
    (r,) = template.find_resources("AWS::BedrockAgentCore::Runtime").values()
    return r["Properties"]


def test_runtime_basics(template):
    r = _runtime(template)
    assert r["AgentRuntimeName"] == RUNTIME_NAME
    assert r["NetworkConfiguration"] == {"NetworkMode": "PUBLIC"}
    assert r["ProtocolConfiguration"] == "HTTP"
    assert "ContainerUri" in r["AgentRuntimeArtifact"]["ContainerConfiguration"]


def test_runtime_accepts_only_our_cognito_access_tokens(template):
    jwt = _runtime(template)["AuthorizerConfiguration"]["CustomJWTAuthorizer"]
    assert "openid-configuration" in str(jwt["DiscoveryUrl"])
    assert len(jwt["AllowedClients"]) == 1
    assert "AllowedAudience" not in jwt


def test_token_forwarded_to_container(template):
    assert _runtime(template)["RequestHeaderConfiguration"] == {"RequestHeaderAllowlist": ["Authorization"]}


def test_role_trusted_only_by_agentcore_in_this_account(template):
    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": [
                    Match.object_like(
                        {
                            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                            "Condition": Match.object_like(
                                {"StringEquals": {"aws:SourceAccount": "123456789012"}}
                            ),
                        }
                    )
                ]
            }
        },
    )


def test_runtime_arn_output(template):
    assert "AgentRuntimeArn" in template.find_outputs("*")


def test_cdk_nag_clean(stack):
    errors = Annotations.from_stack(stack).find_error("*", Match.string_like_regexp("AwsSolutions-.*"))
    assert errors == [], errors


# --- piece 3: model, guardrail, data access, tracing ---------------------------


def _policy_statements(template) -> list[dict]:
    out = []
    for p in template.find_resources("AWS::IAM::Policy").values():
        if any("RuntimeRole" in r["Ref"] for r in p["Properties"]["Roles"]):
            out += p["Properties"]["PolicyDocument"]["Statement"]
    return out


def _stmt(template, action: str, resource_hint: str = "") -> dict:
    for s in _policy_statements(template):
        actions = s["Action"] if isinstance(s["Action"], list) else [s["Action"]]
        if action in actions and resource_hint in str(s["Resource"]):
            return s
    raise AssertionError(f"no statement with {action} {resource_hint}")


def test_runtime_env_and_lifecycle(template):
    r = _runtime(template)
    env = r["EnvironmentVariables"]
    assert env["MODEL_ID"] == "us.amazon.nova-2-lite-v1:0"
    assert env["CHAT_DAILY_LIMIT"] == "50"  # customers and owners
    assert "Fn::GetAtt" in env["GUARDRAIL_ID"] and "Fn::GetAtt" in env["GUARDRAIL_VERSION"]
    assert env["OTEL_SEMCONV_STABILITY_OPT_IN"] == "gen_ai_unredacted_attributes="  # no message text in traces
    assert env["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] == "false"
    assert r["LifecycleConfiguration"] == {"IdleRuntimeSessionTimeout": 900}


def _guardrails(template) -> dict:
    return {g["Properties"]["Name"]: g["Properties"] for g in template.find_resources("AWS::Bedrock::Guardrail").values()}


def test_guardrail_strict_standard_tier(template):
    p = _guardrails(template)["sumaat-chat"]  # customers
    filters = {f["Type"]: (f["InputStrength"], f["OutputStrength"]) for f in p["ContentPolicyConfig"]["FiltersConfig"]}
    assert filters == {
        "HATE": ("HIGH", "HIGH"), "INSULTS": ("HIGH", "HIGH"), "SEXUAL": ("HIGH", "HIGH"),
        "VIOLENCE": ("HIGH", "HIGH"), "MISCONDUCT": ("HIGH", "HIGH"), "PROMPT_ATTACK": ("HIGH", "NONE"),
    }
    assert p["ContentPolicyConfig"]["ContentFiltersTierConfig"] == {"TierName": "STANDARD"}
    assert p["TopicPolicyConfig"]["TopicsTierConfig"] == {"TierName": "STANDARD"}
    assert "guardrail-profile/us.guardrail.v1:0" in str(p["CrossRegionConfig"])
    assert {t["Name"] for t in p["TopicPolicyConfig"]["TopicsConfig"]} == {
        "Medical-advice", "Politics-and-religion-debates", "Financial-and-legal-advice", "Other-food-apps"
    }
    assert all(t["Type"] == "DENY" for t in p["TopicPolicyConfig"]["TopicsConfig"])
    assert p["WordPolicyConfig"]["ManagedWordListsConfig"] == [{"Type": "PROFANITY"}]
    pii = {e["Type"]: e["Action"] for e in p["SensitiveInformationPolicyConfig"]["PiiEntitiesConfig"]}
    assert pii == {"EMAIL": "ANONYMIZE", "PHONE": "ANONYMIZE", "CREDIT_DEBIT_CARD_NUMBER": "BLOCK",
                   "CREDIT_DEBIT_CARD_CVV": "BLOCK", "CREDIT_DEBIT_CARD_EXPIRY": "BLOCK"}
    (iban,) = p["SensitiveInformationPolicyConfig"]["RegexesConfig"]
    assert iban["Action"] == "BLOCK"
    assert p["BlockedInputMessaging"] == p["BlockedOutputsMessaging"] == "[SUMAAT_BLOCKED]"


def test_owner_guardrail_is_the_same_minus_financial_advice(template):
    g = _guardrails(template)
    customer, owner = g["sumaat-chat"], g["sumaat-owner-chat"]
    for key in ("ContentPolicyConfig", "WordPolicyConfig", "SensitiveInformationPolicyConfig", "CrossRegionConfig",
                "BlockedInputMessaging", "BlockedOutputsMessaging"):
        assert owner[key] == customer[key], key
    assert {t["Name"] for t in owner["TopicPolicyConfig"]["TopicsConfig"]} == {
        "Medical-advice", "Politics-and-religion-debates", "Other-food-apps"
    }


def test_guardrail_versions_follow_settings(template):
    from infra.guardrail import OWNER_DENIED_TOPICS, settings_fingerprint

    descriptions = {v["Properties"]["Description"] for v in template.find_resources("AWS::Bedrock::GuardrailVersion").values()}
    assert descriptions == {f"settings {settings_fingerprint()}", f"settings {settings_fingerprint(OWNER_DENIED_TOPICS)}"}


def test_runtime_knows_both_guardrails(template):
    env = _runtime(template)["EnvironmentVariables"]
    assert "Fn::GetAtt" in str(env["OWNER_GUARDRAIL_ID"]) and "Fn::GetAtt" in str(env["OWNER_GUARDRAIL_VERSION"])
    apply = _stmt(template, "bedrock:ApplyGuardrail")
    assert len([r for r in apply["Resource"] if "GuardrailArn" in str(r)]) == 2


def test_topic_limits():
    # Bedrock limits: definition <= 200 chars, <= 5 examples of <= 100 chars.
    from infra.guardrail import DENIED_TOPICS

    for name, (definition, examples) in DENIED_TOPICS.items():
        assert len(definition) <= 200, name
        assert len(examples) <= 5 and all(len(e) <= 100 for e in examples), name


def test_model_access_is_nova_2_lite_only(template):
    s = _stmt(template, "bedrock:InvokeModelWithResponseStream")
    res = str(s["Resource"])
    assert "inference-profile/us.amazon.nova-2-lite-v1:0" in res
    for region in ("us-east-1", "us-east-2", "us-west-2"):
        assert f"arn:aws:bedrock:{region}::foundation-model/amazon.nova-2-lite-v1:0" in res
    assert "*" not in res


def test_dynamodb_access_limited_by_partition_key(template):
    reads = _stmt(template, "dynamodb:GetItem")
    assert reads["Condition"] == {
        "ForAllValues:StringLike": {"dynamodb:LeadingKeys": ["RESTAURANT#*", "CONFIG", "CHATQUOTA#*", "OWNER#*"]}
    }
    gsi1 = [s for s in _policy_statements(template) if "/index/GSI1" in str(s["Resource"])]
    assert len(gsi1) == 2
    geo = next(s for s in gsi1 if "GEO#*" in str(s["Condition"]))
    assert geo["Condition"] == {"ForAllValues:StringLike": {"dynamodb:LeadingKeys": ["GEO#*"]}}
    # Owner assistant: a restaurant's orders, non-personal fields only, and it must name them.
    orders = next(s for s in gsi1 if "RORDERS#*" in str(s["Condition"]))
    assert orders["Action"] == "dynamodb:Query"
    assert orders["Condition"]["ForAllValues:StringLike"] == {"dynamodb:LeadingKeys": ["RORDERS#*"]}
    fields = set(orders["Condition"]["ForAllValues:StringEquals"]["dynamodb:Attributes"])
    assert {"status", "items", "statusHistory", "totalHalalas", "PK", "SK", "GSI1PK", "GSI1SK"} <= fields
    assert not fields & {"customerName", "customerPhone", "customerEmail", "customerSub", "note"}
    assert orders["Condition"]["StringEqualsIfExists"] == {"dynamodb:Select": "SPECIFIC_ATTRIBUTES"}
    write = _stmt(template, "dynamodb:UpdateItem")
    assert write["Condition"] == {"ForAllValues:StringLike": {"dynamodb:LeadingKeys": ["CHATQUOTA#*"]}}
    every = [a for s in _policy_statements(template) for a in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])]
    for forbidden in ("dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:Scan", "dynamodb:BatchGetItem", "dynamodb:*"):
        assert forbidden not in every


def test_metrics_limited_to_agentcore_namespace(template):
    s = _stmt(template, "cloudwatch:PutMetricData")
    assert s["Condition"] == {"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}}


def test_runtime_logs_kept_one_month(template):
    template.has_resource_properties("Custom::LogRetention", {"RetentionInDays": 30})
