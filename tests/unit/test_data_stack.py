import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Annotations, Match, Template

from infra.common import apply_project_guards
from infra.data_stack import DataStack


@pytest.fixture(scope="module")
def stack() -> DataStack:
    app = cdk.App()
    s = DataStack(app, "SumaatData", env=cdk.Environment(region="us-east-1"))
    apply_project_guards(app)
    app.synth()  # runs aspects (tags + cdk-nag)
    return s


@pytest.fixture(scope="module")
def template(stack) -> Template:
    return Template.from_stack(stack)


def test_table_keys_billing_stream_pitr(template):
    template.resource_count_is("AWS::DynamoDB::Table", 1)
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "sumaat",
            "BillingMode": "PAY_PER_REQUEST",
            "KeySchema": [
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            "StreamSpecification": {"StreamViewType": "NEW_AND_OLD_IMAGES"},
            "PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True},
        },
    )


@pytest.mark.parametrize("n", [1, 2])
def test_gsis(template, n):
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "GlobalSecondaryIndexes": Match.array_with(
                [
                    {
                        "IndexName": f"GSI{n}",
                        "KeySchema": [
                            {"AttributeName": f"GSI{n}PK", "KeyType": "HASH"},
                            {"AttributeName": f"GSI{n}SK", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ]
            )
        },
    )


def test_removal_policy_destroy(template):
    template.has_resource(
        "AWS::DynamoDB::Table",
        {"DeletionPolicy": "Delete", "UpdateReplacePolicy": "Delete"},
    )


def test_project_tag(template):
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {"Tags": Match.array_with([{"Key": "project", "Value": "sumaat"}])},
    )


def test_cdk_nag_clean(stack):
    errors = Annotations.from_stack(stack).find_error("*", Match.string_like_regexp("AwsSolutions-.*"))
    assert errors == [], errors
