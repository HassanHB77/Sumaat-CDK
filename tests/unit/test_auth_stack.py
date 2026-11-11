import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Annotations, Match, Template

from infra.auth_stack import AuthStack
from infra.common import apply_project_guards


def _synth(context: dict | None = None) -> AuthStack:
    app = cdk.App(context=context or {})
    stack = AuthStack(app, "SumaatAuth", env=cdk.Environment(account="123456789012", region="us-east-1"))
    apply_project_guards(app)
    app.synth()
    return stack


@pytest.fixture(scope="module")
def stack() -> AuthStack:
    return _synth()


@pytest.fixture(scope="module")
def template(stack) -> Template:
    return Template.from_stack(stack)


def test_two_pools(template):
    template.resource_count_is("AWS::Cognito::UserPool", 2)


def test_business_pool(template):
    template.has_resource_properties(
        "AWS::Cognito::UserPool",
        {
            "UserPoolName": "sumaat-business",
            "UsernameAttributes": ["email"],
            "AutoVerifiedAttributes": ["email"],
            "UserPoolTier": "ESSENTIALS",
            "MfaConfiguration": "OFF",
            "Schema": Match.array_with(
                [
                    Match.object_like({"Name": "email", "Required": True}),
                    Match.object_like({"Name": "name", "Required": True}),
                    Match.object_like({"Name": "restaurantId", "AttributeDataType": "String", "Mutable": True}),
                ]
            ),
            "LambdaConfig": {"PostConfirmation": Match.any_value()},
        },
    )


def test_customer_pool(template):
    template.has_resource_properties(
        "AWS::Cognito::UserPool",
        {
            "UserPoolName": "sumaat-customers",
            "UsernameAttributes": ["phone_number"],
            "UserPoolTier": "ESSENTIALS",
            "Schema": Match.array_with(
                [
                    Match.object_like({"Name": "name", "Required": True}),
                    Match.object_like({"Name": "phone_number", "Required": True}),
                ]
            ),
            "LambdaConfig": {
                "PreSignUp": Match.any_value(),
                "DefineAuthChallenge": Match.any_value(),
                "CreateAuthChallenge": Match.any_value(),
                "VerifyAuthChallengeResponse": Match.any_value(),
            },
        },
    )


@pytest.mark.parametrize("group", ["owner", "cashier"])
def test_business_groups(template, group):
    template.has_resource_properties("AWS::Cognito::UserPoolGroup", {"GroupName": group})


def _clients(template):
    return template.find_resources("AWS::Cognito::UserPoolClient")


def test_business_client_cannot_write_restaurant_id(template):
    (business,) = [
        c["Properties"] for c in _clients(template).values()
        if "custom:restaurantId" in c["Properties"].get("ReadAttributes", [])
    ]
    assert "custom:restaurantId" not in business["WriteAttributes"]
    assert "name" in business["ReadAttributes"] and "name" in business["WriteAttributes"]
    assert business["ExplicitAuthFlows"] == ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
    assert business["GenerateSecret"] is False


def test_customer_client_custom_auth_only(template):
    template.has_resource_properties(
        "AWS::Cognito::UserPoolClient",
        {
            "ExplicitAuthFlows": ["ALLOW_CUSTOM_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
            "GenerateSecret": False,
        },
    )


def test_functions_python314_arm64(template):
    template.resource_count_is("AWS::Lambda::Function", 2)
    template.all_resources_properties(
        "AWS::Lambda::Function", {"Runtime": "python3.14", "Architectures": ["arm64"]}
    )


def test_otp_mode_defaults_to_fixed(template):
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {"Environment": {"Variables": {"OTP_MODE": "fixed", "FIXED_OTP": "1234"}}},
    )


def test_otp_mode_from_context():
    t = Template.from_stack(_synth({"otpMode": "sms"}))
    t.has_resource_properties(
        "AWS::Lambda::Function", {"Environment": {"Variables": Match.object_like({"OTP_MODE": "sms"})}}
    )


def test_bad_otp_mode_rejected():
    with pytest.raises(ValueError):
        _synth({"otpMode": "email"})


def test_project_tag(template):
    template.has_resource_properties(
        "AWS::Cognito::UserPool",
        {"UserPoolTags": Match.object_like({"project": "sumaat"})},
    )


def test_cdk_nag_clean(stack):
    errors = Annotations.from_stack(stack).find_error("*", Match.string_like_regexp("AwsSolutions-.*"))
    assert errors == [], errors
