"""NotifyStack: email the customer when their order becomes READY_FOR_PICKUP.

    order status ACCEPTED -> READY_FOR_PICKUP (cashier taps Ready)
      -> DynamoDB Stream (table `sumaat`, NEW_AND_OLD_IMAGES)
      -> event filter (Lambda only runs for exactly that change on ORDER items)
      -> NotifyFn -> Amazon SES -> customer inbox
    Failed records (after 2 retries) go to an encrypted SQS dead-letter queue.

The sender address lives in SSM Parameter Store (/sumaat/notify/sender), not in the repo.
"""

from pathlib import Path

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sqs as sqs
from cdk_nag import NagSuppressions
from constructs import Construct

FUNCTIONS_DIR = Path(__file__).resolve().parent.parent / "functions"
SENDER_PARAM = "/sumaat/notify/sender"

# Only this change triggers the Lambda (DynamoDB JSON shape of the stream record).
READY_FILTER = {
    "eventName": ["MODIFY"],
    "dynamodb": {
        "NewImage": {"type": {"S": ["ORDER"]}, "status": {"S": ["READY_FOR_PICKUP"]}},
        "OldImage": {"status": {"S": ["ACCEPTED"]}},
    },
}


class NotifyStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, table: dynamodb.ITable, site_domain: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        mode = self.node.try_get_context("notifyMode") or "email"
        if mode not in ("email", "log"):
            raise ValueError(f"notifyMode must be 'email' or 'log', got {mode!r}")

        fn = lambda_.Function(
            self,
            "NotifyFn",
            runtime=lambda_.Runtime.PYTHON_3_14,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.handler",
            code=lambda_.Code.from_asset(str(FUNCTIONS_DIR / "notify")),
            memory_size=256,
            timeout=Duration.seconds(30),
            environment={
                "TABLE_NAME": table.table_name,
                "NOTIFY_MODE": mode,
                "SITE_URL": f"https://{site_domain}",
                "SENDER_PARAM": SENDER_PARAM,
            },
            log_group=logs.LogGroup(
                self, "NotifyFnLogs", retention=logs.RetentionDays.ONE_MONTH, removal_policy=RemovalPolicy.DESTROY
            ),
        )

        dlq = sqs.Queue(
            self,
            "NotifyDlq",
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            retention_period=Duration.days(14),
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.fn, self.dlq = fn, dlq  # for the SumaatOps dashboard

        fn.add_event_source(
            sources.DynamoEventSource(
                table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=10,
                retry_attempts=2,
                max_record_age=Duration.hours(1),
                report_batch_item_failures=True,
                on_failure=sources.SqsDlq(dlq),
                filters=[lambda_.FilterCriteria.filter(READY_FILTER)],
            )
        )

        # Least privilege: mark the order (exactly-once), read the sender, send from this account's identities.
        fn.add_to_role_policy(iam.PolicyStatement(actions=["dynamodb:UpdateItem"], resources=[table.table_arn]))
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter{SENDER_PARAM}"],
            )
        )
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail"],
                resources=[f"arn:aws:ses:{self.region}:{self.account}:identity/*"],
            )
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS-managed AWSLambdaBasicExecutionRole (CloudWatch Logs only) for the notifier Lambda.",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "SES sandbox: the sender AND every recipient are SES identities, so SendEmail needs "
                    "this account's identities (identity/*), same account + region only. The DynamoDB stream read "
                    "grant from the event source covers only this table's stream.",
                },
                {
                    "id": "AwsSolutions-SQS3",
                    "reason": "This queue IS the dead-letter queue (on-failure destination of the stream event source).",
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Python 3.14 is pinned project-wide (.python-version) so local tests match the Lambda "
                    "runtime; upgrade together later.",
                },
            ],
        )
