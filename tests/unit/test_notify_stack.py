import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Annotations, Match, Template

from infra.common import apply_project_guards
from infra.data_stack import DataStack
from infra.notify_stack import READY_FILTER, NotifyStack

ENV = cdk.Environment(account="123456789012", region="us-east-1")


def _synth(context=None) -> NotifyStack:
    app = cdk.App(context=context or {})
    data = DataStack(app, "SumaatData", env=ENV)
    stack = NotifyStack(app, "SumaatNotify", table=data.table, site_domain="dxxxx.cloudfront.net", env=ENV)
    apply_project_guards(app)
    app.synth()
    return stack


@pytest.fixture(scope="module")
def stack():
    return _synth()


@pytest.fixture(scope="module")
def template(stack):
    return Template.from_stack(stack)


def test_lambda(template):
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.14",
            "Architectures": ["arm64"],
            "Environment": {
                "Variables": Match.object_like(
                    {"NOTIFY_MODE": "email", "SITE_URL": "https://dxxxx.cloudfront.net", "SENDER_PARAM": "/sumaat/notify/sender"}
                )
            },
        },
    )


def test_stream_source_with_ready_filter(template):
    import json

    (mapping,) = template.find_resources("AWS::Lambda::EventSourceMapping").values()
    p = mapping["Properties"]
    assert p["StartingPosition"] == "LATEST"
    assert p["MaximumRetryAttempts"] == 2
    assert p["FunctionResponseTypes"] == ["ReportBatchItemFailures"]
    assert "DestinationConfig" in p
    (flt,) = p["FilterCriteria"]["Filters"]
    assert json.loads(flt["Pattern"]) == READY_FILTER


def test_dlq_encrypted(template):
    template.has_resource_properties("AWS::SQS::Queue", {"SqsManagedSseEnabled": True})


def test_iam_least_privilege(template):
    statements = [s for p in template.find_resources("AWS::IAM::Policy").values() for s in p["Properties"]["PolicyDocument"]["Statement"]]
    actions = {a for s in statements for a in ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])}
    assert {"ses:SendEmail", "ssm:GetParameter", "dynamodb:UpdateItem"} <= actions
    assert not any(a in actions for a in ("ses:*", "dynamodb:*", "ssm:*"))
    ssm = next(s for s in statements if s["Action"] == "ssm:GetParameter")
    assert "parameter/sumaat/notify/sender" in str(ssm["Resource"])


def test_log_mode_from_context():
    t = Template.from_stack(_synth({"notifyMode": "log"}))
    t.has_resource_properties("AWS::Lambda::Function", {"Environment": {"Variables": Match.object_like({"NOTIFY_MODE": "log"})}})


def test_bad_mode_rejected():
    with pytest.raises(ValueError):
        _synth({"notifyMode": "sms"})


def test_cdk_nag_clean(stack):
    errors = Annotations.from_stack(stack).find_error("*", Match.string_like_regexp("AwsSolutions-.*"))
    assert errors == [], errors
