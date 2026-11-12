"""AgentStack: the Sumaat AI assistant on Amazon Bedrock AgentCore Runtime (Step 9).

    Browser --POST /agent/chat--> CloudFront (WebStack) --> AgentCore Runtime endpoint
                                                              | checks the Cognito ACCESS token itself
                                                              v   (issuer = our pool, client_id = web client)
                                                        container from agent/Dockerfile (arm64, port 8080)

AgentCore runs each chat session in its own small VM and streams our replies (SSE) back to the browser.
The container image is built from agent/ (+ api/, reused for restaurants and menus) and pushed to ECR by CDK.

SPIKE (piece 0): no model / DynamoDB permissions yet; pieces 1-3 add them.
"""

from pathlib import Path

from aws_cdk import CfnOutput, IgnoreMode, Stack
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from cdk_nag import NagSuppressions
from constructs import Construct

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_NAME = "sumaat_agent"  # letters, digits, underscores only


class AgentStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
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
        image.repository.grant_pull(role)  # also adds ecr:GetAuthorizationToken (account-wide by design)
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*"
                ],
            )
        )

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
        )
        runtime.node.add_dependency(role)  # the role's policy must exist before AgentCore pulls the image

        self.runtime_arn = runtime.attr_agent_runtime_arn
        CfnOutput(self, "AgentRuntimeArn", value=self.runtime_arn)

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "ecr:GetAuthorizationToken only works on '*' (AWS design); log permissions are "
                    "limited to the AgentCore runtimes log groups in this account.",
                },
            ],
        )
