"""SumaatOps: one CloudWatch dashboard + alarms for the whole app.

Dashboard only (POC decision): the alarms turn red on the dashboard and in the CloudWatch console but send
nothing (no SNS / email). Add an SNS action later if someone should be paged.

Rows: API, Lambdas, pickup email, AI chat (AgentCore), DynamoDB, alarm status.
Missing data counts as OK, so a quiet night never looks like an outage.
"""

from aws_cdk import Duration, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from infra.agent_stack import RUNTIME_NAME

DASHBOARD_NAME = "Sumaat"
FIVE_MIN = Duration.minutes(5)
AGENT_NAMESPACE = "AWS/Bedrock-AgentCore"
API_LATENCY_P90_MS = 3_000
AI_DURATION_P90_MS = 20_000  # a reply with a second search takes ~14 s; 20 s means something is wrong
DDB_OPERATIONS = [
    dynamodb.Operation.GET_ITEM,
    dynamodb.Operation.PUT_ITEM,
    dynamodb.Operation.UPDATE_ITEM,
    dynamodb.Operation.QUERY,
    dynamodb.Operation.TRANSACT_WRITE_ITEMS,
]


class OpsStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        api: apigw.RestApi,
        api_fn: lambda_.IFunction,
        notify_fn: lambda_.IFunction,
        notify_dlq: sqs.IQueue,
        auth_fns: list[lambda_.IFunction],
        table: dynamodb.ITable,
        agent_runtime_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        def agent_metric(name: str, statistic: str) -> cw.Metric:
            # Dimensions as AgentCore publishes them for one runtime endpoint (checked in the live account).
            return cw.Metric(
                namespace=AGENT_NAMESPACE,
                metric_name=name,
                dimensions_map={
                    "Resource": agent_runtime_arn,
                    "Operation": "InvokeAgentRuntime",
                    "Name": f"{RUNTIME_NAME}::DEFAULT",
                },
                statistic=statistic,
                period=FIVE_MIN,
            )

        # --- metrics ---------------------------------------------------------------
        api_requests = api.metric_count(period=FIVE_MIN, statistic="Sum", label="Requests")
        api_4xx = api.metric_client_error(period=FIVE_MIN, statistic="Sum", label="4XX")
        api_5xx = api.metric_server_error(period=FIVE_MIN, statistic="Sum", label="5XX")
        api_p50 = api.metric_latency(period=FIVE_MIN, statistic="p50", label="p50")
        api_p90 = api.metric_latency(period=FIVE_MIN, statistic="p90", label="p90")

        api_fn_errors = api_fn.metric_errors(period=FIVE_MIN, label="API errors")
        notify_errors = notify_fn.metric_errors(period=FIVE_MIN, label="Notify errors")
        dlq_visible = notify_dlq.metric_approximate_number_of_messages_visible(
            period=FIVE_MIN, statistic="Maximum", label="Failed emails waiting (DLQ)"
        )

        ai_invocations = agent_metric("Invocations", "Sum").with_(label="Chat messages")
        ai_errors = agent_metric("Errors", "Sum").with_(label="Errors")
        ai_p50 = agent_metric("Duration", "p50").with_(label="p50")
        ai_p90 = agent_metric("Duration", "p90").with_(label="p90")

        # --- alarms (no actions: dashboard only) ----------------------------------------
        def alarm(cid: str, metric: cw.IMetric, threshold: float, description: str, periods: int = 1) -> cw.Alarm:
            return cw.Alarm(
                self,
                cid,
                alarm_name=f"sumaat-{cid}",
                alarm_description=description,
                metric=metric,
                threshold=threshold,
                evaluation_periods=periods,
                comparison_operator=cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
            )

        self.alarms = [
            alarm("api-5xx", api_5xx, 1, "The API returned a server error (5XX) in the last 5 minutes."),
            alarm(
                "api-latency-p90",
                api_p90,
                API_LATENCY_P90_MS,
                "API p90 latency has been 3 s or more for 15 minutes.",
                periods=3,
            ),
            alarm("api-fn-errors", api_fn_errors, 1, "The API Lambda raised an error."),
            alarm("notify-errors", notify_errors, 1, "The pickup-email Lambda raised an error."),
            alarm("notify-dlq", dlq_visible, 1, "A pickup email failed after retries and is waiting in the DLQ."),
            alarm("ai-errors", ai_errors, 1, "The AI assistant (AgentCore runtime) returned an error."),
            alarm(
                "ai-duration-p90",
                ai_p90,
                AI_DURATION_P90_MS,
                "AI replies p90 took 20 s or more in the last 5 minutes.",
            ),
        ]

        # --- dashboard -------------------------------------------------------------
        def graph(title: str, left: list[cw.IMetric], unit_label: str = "", width: int = 8) -> cw.GraphWidget:
            return cw.GraphWidget(
                title=title, left=left, width=width, height=6, left_y_axis=cw.YAxisProps(label=unit_label, min=0)
            )

        def header(text: str) -> cw.TextWidget:
            return cw.TextWidget(markdown=f"### {text}", width=24, height=1)

        auth_errors = [f.metric_errors(period=FIVE_MIN) for f in auth_fns]
        ddb_throttles = table.metric_throttled_requests_for_operations(
            operations=DDB_OPERATIONS, period=FIVE_MIN, label="Throttled requests"
        )
        ddb_system_errors = table.metric_system_errors_for_operations(
            operations=DDB_OPERATIONS, period=FIVE_MIN, label="System errors"
        )

        cw.Dashboard(
            self,
            "Dashboard",
            dashboard_name=DASHBOARD_NAME,
            default_interval=Duration.hours(3),
            widgets=[
                [header("API (API Gateway, behind CloudFront /api)")],
                [
                    graph("Requests", [api_requests], "count"),
                    graph("Errors (4XX / 5XX)", [api_4xx, api_5xx], "count"),
                    graph("Latency", [api_p50, api_p90], "ms"),
                ],
                [header("Lambdas")],
                [
                    graph("API Lambda errors", [api_fn_errors], "count"),
                    graph(
                        "API Lambda duration",
                        [api_fn.metric_duration(period=FIVE_MIN, statistic="p90", label="p90")],
                        "ms",
                    ),
                    graph("Sign-up triggers errors (PreSignUp, PostConfirmation)", auth_errors, "count"),
                ],
                [header("Pickup email (order Ready -> email)")],
                [
                    graph(
                        "Notify Lambda",
                        [notify_fn.metric_invocations(period=FIVE_MIN, label="Runs"), notify_errors],
                        "count",
                    ),
                    graph("Failed emails (dead-letter queue)", [dlq_visible], "messages"),
                ],
                [header("AI assistant (Bedrock AgentCore runtime)")],
                [
                    graph("Chat messages", [ai_invocations], "count"),
                    graph("Errors", [ai_errors], "count"),
                    graph("Reply time", [ai_p50, ai_p90], "ms"),
                ],
                [header("DynamoDB (table sumaat)")],
                [
                    graph(
                        "Capacity used",
                        [
                            table.metric_consumed_read_capacity_units(period=FIVE_MIN, label="Read units"),
                            table.metric_consumed_write_capacity_units(period=FIVE_MIN, label="Write units"),
                        ],
                        "units",
                    ),
                    # Separate graphs: both math expressions use the same per-operation ids (getitem, ...).
                    graph("Throttled requests", [ddb_throttles], "count"),
                    graph("System errors", [ddb_system_errors], "count"),
                ],
                [cw.AlarmStatusWidget(title="Alarms", alarms=self.alarms, width=24, height=4)],
            ],
        )
