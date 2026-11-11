import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Annotations, Match, Template

from infra.auth_stack import AuthStack
from infra.common import apply_project_guards


@pytest.fixture(scope="module")
def stack() -> AuthStack:
    app = cdk.App()
    stack = AuthStack(app, "SumaatAuth", env=cdk.Environment(account="123456789012", region="us-east-1"))
    apply_project_guards(app)
    app.synth()
    return stack


@pytest.fixture(scope="module")
def template(stack) -> Template:
    return Template.from_stack(stack)


def test_one_pool(template):
    template.resource_count_is("AWS::Cognito::UserPool", 1)


def test_pool_email_password_with_required_phone(template):
    template.has_resource_properties(
        "AWS::Cognito::UserPool",
        {
            "UserPoolName": "sumaat-users",
            "UsernameAttributes": ["email"],
            "AutoVerifiedAttributes": ["email"],
            "UserPoolTier": "ESSENTIALS",
            "MfaConfiguration": "OFF",
            "Schema": Match.array_with(
                [
                    Match.object_like({"Name": "email", "Required": True}),
                    Match.object_like({"Name": "name", "Required": True}),
                    Match.object_like({"Name": "phone_number", "Required": True}),
                    Match.object_like({"Name": "restaurantId", "AttributeDataType": "String", "Mutable": True}),
                    Match.object_like({"Name": "signupRole", "AttributeDataType": "String", "Mutable": True}),
                ]
            ),
            "LambdaConfig": {"PostConfirmation": Match.any_value()},
        },
    )


def test_no_sms_or_custom_auth_left(template):
    pool = next(iter(template.find_resources("AWS::Cognito::UserPool").values()))["Properties"]
    assert set(pool["LambdaConfig"]) == {"PostConfirmation"}
    assert "SmsConfiguration" not in pool


@pytest.mark.parametrize("group", ["customer", "owner", "cashier"])
def test_groups(template, group):
    template.has_resource_properties("AWS::Cognito::UserPoolGroup", {"GroupName": group})


def test_client(template):
    clients = template.find_resources("AWS::Cognito::UserPoolClient")
    assert len(clients) == 1
    client = next(iter(clients.values()))["Properties"]
    assert sorted(client["ExplicitAuthFlows"]) == [
        "ALLOW_REFRESH_TOKEN_AUTH",
        "ALLOW_USER_PASSWORD_AUTH",
        "ALLOW_USER_SRP_AUTH",
    ]
    assert client["GenerateSecret"] is False
    assert "custom:restaurantId" in client["ReadAttributes"]
    assert "custom:restaurantId" not in client["WriteAttributes"]  # only the API sets it
    for attr in ("email", "name", "phone_number", "custom:signupRole"):
        assert attr in client["WriteAttributes"]


def test_one_function_python314_arm64(template):
    template.resource_count_is("AWS::Lambda::Function", 1)
    template.all_resources_properties(
        "AWS::Lambda::Function", {"Runtime": "python3.14", "Architectures": ["arm64"]}
    )


def test_outputs(template):
    outputs = template.find_outputs("*")
    assert {"UserPoolId", "UserPoolClientId"} <= set(outputs)


def test_project_tag(template):
    template.has_resource_properties(
        "AWS::Cognito::UserPool",
        {"UserPoolTags": Match.object_like({"project": "sumaat"})},
    )


def test_cdk_nag_clean(stack):
    errors = Annotations.from_stack(stack).find_error("*", Match.string_like_regexp("AwsSolutions-.*"))
    assert errors == [], errors
