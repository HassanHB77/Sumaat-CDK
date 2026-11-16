import json

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Annotations, Match, Template

from infra.api_stack import ApiStack
from infra.auth_stack import AuthStack
from infra.common import apply_project_guards
from infra.data_stack import DataStack
from infra.notify_stack import NotifyStack
from infra.ops_stack import DASHBOARD_NAME, OpsStack

ENV = cdk.Environment(account="123456789012", region="us-east-1")
AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/sumaat_agent-abc123"


@pytest.fixture(scope="module")
def stack() -> OpsStack:
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})  # no Docker in unit tests
    data = DataStack(app, "SumaatData", env=ENV)
    auth = AuthStack(app, "SumaatAuth", env=ENV)
    api = ApiStack(app, "SumaatApi", table=data.table, user_pool=auth.user_pool, env=ENV)
    notify = NotifyStack(app, "SumaatNotify", table=data.table, site_domain="d123.cloudfront.net", env=ENV)
    ops = OpsStack(
        app,
        "SumaatOps",
        api=api.api,
        api_fn=api.fn,
        notify_fn=notify.fn,
        notify_dlq=notify.dlq,
        auth_fns=auth.trigger_fns,
        table=data.table,
        agent_runtime_arn=AGENT_ARN,
        env=ENV,
    )
    apply_project_guards(app)
    app.synth()
    return ops


@pytest.fixture(scope="module")
def template(stack) -> Template:
    return Template.from_stack(stack)


def _dashboard_body(template) -> str:
    """DashboardBody is a Fn::Join of strings and tokens; keep only the literal strings."""
    (dash,) = template.find_resources("AWS::CloudWatch::Dashboard").values()
    body = dash["Properties"]["DashboardBody"]
    return "".join(p for p in body["Fn::Join"][1] if isinstance(p, str)) if isinstance(body, dict) else body


def test_one_dashboard(template):
    template.resource_count_is("AWS::CloudWatch::Dashboard", 1)
    template.has_resource_properties("AWS::CloudWatch::Dashboard", {"DashboardName": DASHBOARD_NAME})


def test_seven_alarms_without_actions(template):
    alarms = template.find_resources("AWS::CloudWatch::Alarm")
    assert len(alarms) == 7
    for a in alarms.values():
        props = a["Properties"]
        assert "AlarmActions" not in props, "dashboard only: alarms must not notify"
        assert props["TreatMissingData"] == "notBreaching"
        assert props["AlarmName"].startswith("sumaat-")


def _alarm_metric(template, name: str) -> tuple[dict, dict]:
    """(alarm properties, its MetricStat). Labelled metrics are written in the Metrics-list form."""
    for a in template.find_resources("AWS::CloudWatch::Alarm").values():
        props = a["Properties"]
        if props["AlarmName"] == name:
            (m,) = props["Metrics"]
            return props, m["MetricStat"]
    raise AssertionError(f"no alarm {name}")


def test_ai_alarms_use_the_runtime_dimensions(template):
    _, stat = _alarm_metric(template, "sumaat-ai-errors")
    assert stat["Metric"]["Namespace"] == "AWS/Bedrock-AgentCore"
    assert stat["Metric"]["MetricName"] == "Errors"
    dims = {d["Name"]: d["Value"] for d in stat["Metric"]["Dimensions"]}
    assert dims == {"Resource": AGENT_ARN, "Operation": "InvokeAgentRuntime", "Name": "sumaat_agent::DEFAULT"}

    props, stat = _alarm_metric(template, "sumaat-ai-duration-p90")
    assert (stat["Metric"]["MetricName"], stat["Stat"], props["Threshold"]) == ("Duration", "p90", 20000)


def test_dlq_alarm(template):
    props, stat = _alarm_metric(template, "sumaat-notify-dlq")
    assert stat["Metric"]["Namespace"] == "AWS/SQS"
    assert stat["Metric"]["MetricName"] == "ApproximateNumberOfMessagesVisible"
    assert props["Threshold"] == 1


def test_dashboard_has_every_section(template):
    body = _dashboard_body(template)
    for section in ["API", "Lambdas", "Pickup email", "AI assistant", "DynamoDB"]:
        assert section in body, section
    assert '"type":"alarm"' in body  # alarm status widget
    json.dumps(body)  # serialisable


def test_cdk_nag_clean(stack):
    errors = Annotations.from_stack(stack).find_error("*", Match.string_like_regexp("AwsSolutions-.*"))
    assert errors == [], errors
