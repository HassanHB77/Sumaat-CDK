import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Annotations, Match, Template

from infra.api_stack import ApiStack
from infra.auth_stack import AuthStack
from infra.common import apply_project_guards
from infra.data_stack import DataStack

ENV = cdk.Environment(account="123456789012", region="us-east-1")


@pytest.fixture(scope="module")
def stack() -> ApiStack:
    # Skip Docker bundling in unit tests: we test the template, not the zip.
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})
    data = DataStack(app, "SumaatData", env=ENV)
    auth = AuthStack(app, "SumaatAuth", env=ENV)
    api = ApiStack(app, "SumaatApi", table=data.table, user_pool=auth.user_pool, env=ENV)
    apply_project_guards(app)
    app.synth()
    return api


@pytest.fixture(scope="module")
def template(stack) -> Template:
    return Template.from_stack(stack)


def _methods(template) -> list[dict]:
    return [r["Properties"] for r in template.find_resources("AWS::ApiGateway::Method").values()]


def test_lambda(template):
    template.resource_count_is("AWS::Lambda::Function", 1)
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Handler": "api.handler.handler",
            "Runtime": "python3.14",
            "Architectures": ["arm64"],
            "MemorySize": 512,
            "Timeout": 10,
            "Environment": {
                "Variables": {
                    "TABLE_NAME": Match.any_value(),
                    "USER_POOL_ID": Match.any_value(),
                    "ALLOWED_ORIGINS": "http://localhost:5173",
                    "ENABLE_DOCS": "0",
                }
            },
        },
    )


def test_cognito_authorizer(template):
    template.resource_count_is("AWS::ApiGateway::Authorizer", 1)
    template.has_resource_properties(
        "AWS::ApiGateway::Authorizer",
        {"Type": "COGNITO_USER_POOLS", "IdentitySource": "method.request.header.Authorization"},
    )


def test_only_browse_gets_are_public(template):
    methods = _methods(template)
    public = [m for m in methods if m["AuthorizationType"] == "NONE" and m["HttpMethod"] != "OPTIONS"]
    assert len(public) == 4  # /health, /categories, /restaurants, /restaurants/{id}
    assert all(m["HttpMethod"] == "GET" for m in public)


def test_everything_else_needs_login(template):
    others = [m for m in _methods(template) if m["HttpMethod"] not in ("GET", "OPTIONS")]
    assert len(others) == 4  # ANY on /restaurants, /restaurants/{id}, /restaurants/{id}/{proxy+}, /{proxy+}
    assert all(m["HttpMethod"] == "ANY" for m in others)
    assert all(m["AuthorizationType"] == "COGNITO_USER_POOLS" and "AuthorizerId" in m for m in others)


def test_preflight_is_public_and_has_no_lambda(template):
    options = [m for m in _methods(template) if m["HttpMethod"] == "OPTIONS"]
    assert options, "expected CORS preflight methods"
    assert all(m["AuthorizationType"] == "NONE" and m["Integration"]["Type"] == "MOCK" for m in options)


def test_proxy_resources(template):
    paths = [r["Properties"]["PathPart"] for r in template.find_resources("AWS::ApiGateway::Resource").values()]
    assert paths.count("{proxy+}") == 2
    for p in ("health", "categories", "restaurants", "{id}"):
        assert p in paths


def test_cors_origin_in_preflight(template):
    template.has_resource_properties(
        "AWS::ApiGateway::Method",
        {
            "HttpMethod": "OPTIONS",
            "Integration": Match.object_like(
                {
                    "IntegrationResponses": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "ResponseParameters": Match.object_like(
                                        {"method.response.header.Access-Control-Allow-Origin": "'http://localhost:5173'"}
                                    )
                                }
                            )
                        ]
                    )
                }
            ),
        },
    )


def test_gateway_errors_have_cors(template):
    template.resource_count_is("AWS::ApiGateway::GatewayResponse", 2)


def test_stage_throttling_and_logging(template):
    template.has_resource_properties(
        "AWS::ApiGateway::Stage",
        {
            "StageName": "prod",
            "AccessLogSetting": Match.object_like({"DestinationArn": Match.any_value()}),
            "MethodSettings": Match.array_with(
                [
                    Match.object_like(
                        {
                            "ThrottlingRateLimit": 10,
                            "ThrottlingBurstLimit": 20,
                            "LoggingLevel": "ERROR",
                            "DataTraceEnabled": False,
                        }
                    )
                ]
            ),
        },
    )


def test_cloudwatch_role_is_retained(template):
    template.has_resource("AWS::ApiGateway::Account", {"DeletionPolicy": "Retain"})


def test_iam_least_privilege(template):
    statements = [
        s
        for p in template.find_resources("AWS::IAM::Policy").values()
        for s in p["Properties"]["PolicyDocument"]["Statement"]
    ]
    assert all(s["Resource"] != "*" for s in statements)
    (cognito_stmt,) = [s for s in statements if "cognito-idp:AdminCreateUser" in str(s["Action"])]
    assert sorted(cognito_stmt["Action"]) == sorted(
        f"cognito-idp:{a}"
        for a in (
            "AdminUpdateUserAttributes", "AdminCreateUser", "AdminSetUserPassword", "AdminAddUserToGroup",
            "AdminDisableUser", "AdminEnableUser", "AdminUserGlobalSignOut", "AdminDeleteUser",
        )
    )
    # This pool's ARN only (imported from SumaatAuth), never a wildcard.
    assert "Fn::ImportValue" in str(cognito_stmt["Resource"]) and "*" not in str(cognito_stmt["Resource"])
    assert not any("cognito-idp:*" in str(s["Action"]) for s in statements)


def test_api_url_output(template):
    assert "ApiUrl" in template.find_outputs("*")


def test_cdk_nag_clean(stack):
    errors = Annotations.from_stack(stack).find_error("*", Match.string_like_regexp("AwsSolutions-.*"))
    assert errors == [], errors
