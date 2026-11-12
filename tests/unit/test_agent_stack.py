import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Annotations, Match, Template

from infra.agent_stack import RUNTIME_NAME, AgentStack
from infra.auth_stack import AuthStack
from infra.common import apply_project_guards

ENV = cdk.Environment(account="123456789012", region="us-east-1")


@pytest.fixture(scope="module")
def stack() -> AgentStack:
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})
    auth = AuthStack(app, "SumaatAuth", env=ENV)
    agent = AgentStack(app, "SumaatAgent", user_pool=auth.user_pool, user_pool_client=auth.client, env=ENV)
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
