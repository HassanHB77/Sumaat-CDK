"""AgentStack: the Sumaat AI assistant on Amazon Bedrock AgentCore Runtime (Step 9).

    Browser --POST /agent/chat--> CloudFront (WebStack) --> AgentCore Runtime endpoint
                                                              | checks the Cognito ACCESS token itself
                                                              v   (issuer = our pool, client_id = web client)
                                                        container from agent/Dockerfile (arm64, port 8080)
                                                          Strands agent -> Bedrock: Nova 2 Lite + Guardrail
                                                          tools         -> DynamoDB (restaurants, menus, quota)

AgentCore runs each chat session in its own small VM and streams our replies (SSE) back to the browser.
The container image is built from agent/ (+ api/, reused for restaurants and menus) and pushed to ECR by CDK.

The agent's role can only: use Nova 2 Lite and our guardrail, read restaurant/menu/config rows (not orders or
customers), update its own chat-quota rows, and write logs/traces.
"""

from pathlib import Path

from aws_cdk import CfnOutput, IgnoreMode, Stack
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from cdk_nag import NagSuppressions
from constructs import Construct

from agent.session import DEFAULT_MODEL_ID, IDLE_SECONDS
from api.services.chat_quota import DEFAULT_LIMIT
from api.services.stats import STATS_FIELDS  # the only order fields the owner assistant may read
from infra.guardrail import GUARDRAIL_PROFILE, build_guardrail

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_NAME = "sumaat_agent"  # letters, digits, underscores only
MODEL = DEFAULT_MODEL_ID.removeprefix("us.")  # amazon.nova-2-lite-v1:0
MODEL_REGIONS = ["us-east-1", "us-east-2", "us-west-2"]  # where the "us." inference profile may send a request

# Rows the agent may touch (DynamoDB partition keys; see api/services/*):
# restaurants + menus, categories, its own counters, and the owner -> restaurant lock (owner assistant)
READ_KEYS = ["RESTAURANT#*", "CONFIG", "CHATQUOTA#*", "OWNER#*"]
GEO_INDEX_KEYS = ["GEO#*"]  # GSI1 "near me" cells
ORDER_INDEX_KEYS = ["RORDERS#*"]  # GSI1 restaurant order lists (owner assistant), STATS_FIELDS only
WRITE_KEYS = ["CHATQUOTA#*"]

# AWS OpenTelemetry -> CloudWatch GenAI Observability. Message text is redacted from traces:
# "gen_ai_unredacted_attributes=" (empty list) makes Strands redact every prompt/response/tool attribute.
TRACING_ENV = {
    "AGENT_OBSERVABILITY_ENABLED": "true",
    "OTEL_PYTHON_DISTRO": "aws_distro",
    "OTEL_PYTHON_CONFIGURATOR": "aws_configurator",
    "OTEL_RESOURCE_ATTRIBUTES": "service.name=sumaat-agent",
    "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_unredacted_attributes=",
    "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "false",
}


def _leading_keys(keys: list[str]) -> dict:
    return {"ForAllValues:StringLike": {"dynamodb:LeadingKeys": keys}}


class AgentStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        table: dynamodb.ITable,
        user_pool: cognito.IUserPool,
        user_pool_client: cognito.IUserPoolClient,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        image = ecr_assets.DockerImageAsset(
            self,
            "AgentImage",
            directory=str(ROOT),
            file="agent/Dockerfile",
            platform=ecr_assets.Platform.LINUX_ARM64,
            # Only agent/ and api/ go into the build context (and the asset hash).
            exclude=["*", "!agent", "!api", "**/__pycache__", "**/*.pyc"],
            ignore_mode=IgnoreMode.DOCKER,  # .dockerignore rules: '!' re-includes
        )

        guardrail, guardrail_version = build_guardrail(self, self.region, self.account)

        role = iam.Role(
            self,
            "RuntimeRole",
            description="Sumaat AI agent on Bedrock AgentCore Runtime",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:*"
                    },
                },
            ),
        )
        self._grant(role, image, table, guardrail.attr_guardrail_arn)

        discovery_url = (
            f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}"
            "/.well-known/openid-configuration"
        )
        runtime = agentcore.CfnRuntime(
            self,
            "Runtime",
            agent_runtime_name=RUNTIME_NAME,
            description="Sumaat customer chat assistant",
            role_arn=role.role_arn,
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=image.image_uri
                )
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(network_mode="PUBLIC"),
            protocol_configuration="HTTP",
            # Only Cognito ACCESS tokens from our web client get in; AgentCore rejects everything else (401)
            # before our container runs. (ID tokens have no client_id claim, so they are refused too.)
            authorizer_configuration=agentcore.CfnRuntime.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnRuntime.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=discovery_url,
                    allowed_clients=[user_pool_client.user_pool_client_id],
                )
            ),
            # Pass the (already verified) token on to our code, which reads the user's group from it.
            request_header_configuration=agentcore.CfnRuntime.RequestHeaderConfigurationProperty(
                request_header_allowlist=["Authorization"]
            ),
            # A chat's VM (and its memory) ends after 15 idle minutes, same as agent/session.py.
            lifecycle_configuration=agentcore.CfnRuntime.LifecycleConfigurationProperty(
                idle_runtime_session_timeout=IDLE_SECONDS
            ),
            environment_variables={
                "TABLE_NAME": table.table_name,
                "MODEL_ID": DEFAULT_MODEL_ID,
                "GUARDRAIL_ID": guardrail.attr_guardrail_id,
                "GUARDRAIL_VERSION": guardrail_version.attr_version,
                "CHAT_DAILY_LIMIT": str(DEFAULT_LIMIT),
                **TRACING_ENV,
            },
        )
        runtime.node.add_dependency(role)  # the role's policy must exist before AgentCore pulls the image

        # AgentCore creates the runtime's log group itself (no expiry); keep one month like the other logs.
        logs.LogRetention(
            self,
            "RuntimeLogRetention",
            log_group_name=f"/aws/bedrock-agentcore/runtimes/{runtime.attr_agent_runtime_id}-DEFAULT",
            retention=logs.RetentionDays.ONE_MONTH,
        )

        self.runtime_arn = runtime.attr_agent_runtime_arn
        CfnOutput(self, "AgentRuntimeArn", value=self.runtime_arn)
        CfnOutput(self, "GuardrailId", value=guardrail.attr_guardrail_id)
        self._suppress_nag()

    def _grant(self, role: iam.Role, image: ecr_assets.DockerImageAsset, table: dynamodb.ITable, guardrail_arn: str):
        image.repository.grant_pull(role)  # also adds ecr:GetAuthorizationToken (account-wide by design)
        region, account = self.region, self.account
        statements = [
            # The model: our inference profile + the foundation model in each region it may route to.
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    f"arn:aws:bedrock:{region}:{account}:inference-profile/{DEFAULT_MODEL_ID}",
                    *(f"arn:aws:bedrock:{r}::foundation-model/{MODEL}" for r in MODEL_REGIONS),
                ],
            ),
            # The guardrail (Standard tier runs through the cross-region guardrail profile).
            iam.PolicyStatement(
                actions=["bedrock:ApplyGuardrail"],
                resources=[guardrail_arn, f"arn:aws:bedrock:*:{account}:guardrail-profile/{GUARDRAIL_PROFILE}"],
            ),
            # DynamoDB: only restaurant/menu/config rows and its own quota rows - never orders or customers.
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:Query"],
                resources=[table.table_arn],
                conditions=_leading_keys(READ_KEYS),
            ),
            iam.PolicyStatement(
                actions=["dynamodb:Query"],
                resources=[f"{table.table_arn}/index/GSI1"],
                conditions=_leading_keys(GEO_INDEX_KEYS),
            ),
            # Owner assistant: a restaurant's orders, but ONLY the fields stats need. A query must name its
            # attributes (Select=SPECIFIC_ATTRIBUTES) and may not ask for customer name, phone, email or note.
            iam.PolicyStatement(
                actions=["dynamodb:Query"],
                resources=[f"{table.table_arn}/index/GSI1"],
                conditions={
                    **_leading_keys(ORDER_INDEX_KEYS),
                    "ForAllValues:StringEquals": {"dynamodb:Attributes": list(STATS_FIELDS)},
                    "StringEqualsIfExists": {"dynamodb:Select": "SPECIFIC_ATTRIBUTES"},
                },
            ),
            iam.PolicyStatement(
                actions=["dynamodb:UpdateItem"],
                resources=[table.table_arn],
                conditions=_leading_keys(WRITE_KEYS),
            ),
            # Logs, traces and metrics (what AgentCore observability documents for a runtime role).
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"],
                resources=[f"arn:aws:logs:{region}:{account}:log-group:/aws/bedrock-agentcore/runtimes/*"],
            ),
            iam.PolicyStatement(actions=["logs:DescribeLogGroups"], resources=["*"]),
            iam.PolicyStatement(
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                resources=["*"],
            ),
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}},
            ),
        ]
        for s in statements:
            role.add_to_policy(s)

    def _suppress_nag(self) -> None:
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcards are AWS-required or narrowed: ecr:GetAuthorizationToken, X-Ray trace "
                    "writes and logs:DescribeLogGroups only work on '*'; PutMetricData is limited to the "
                    "bedrock-agentcore namespace; log writes to the AgentCore runtime log groups; the guardrail "
                    "profile ARN has a region wildcard because the Standard tier may run in any US region; "
                    "DynamoDB access is limited by partition-key prefixes (RESTAURANT#, CONFIG, CHATQUOTA#, OWNER#, GEO#, "
                    "RORDERS#); RORDERS# order queries are also limited to the non-personal stats attributes.",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "CDK-managed log-retention helper Lambda uses the AWS-managed basic execution role "
                    "(CloudWatch Logs only).",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ],
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Runtime of the CDK-managed log-retention helper Lambda is chosen by the CDK library.",
                },
            ],
        )
