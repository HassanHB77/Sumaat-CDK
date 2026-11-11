"""ApiStack: the FastAPI app (api/) on Lambda behind an API Gateway REST API.

Secure by default: every route needs a Cognito login (ID token in the Authorization header) EXCEPT the
public browse GETs below. API Gateway rejects missing/invalid tokens with 401 before the Lambda runs;
the app then checks groups and ownership (api/auth.py, api/services/*).
"""

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from cdk_nag import NagSuppressions
from constructs import Construct

API_DIR = Path(__file__).resolve().parent.parent / "api"
RUNTIME = lambda_.Runtime.PYTHON_3_14
DEFAULT_ORIGINS = ["http://localhost:5173"]

# What the API does in Cognito, and why:
COGNITO_ADMIN_ACTIONS = [
    "AdminUpdateUserAttributes",  # POST /restaurants sets the owner's custom:restaurantId
    "AdminCreateUser",  # owner creates a cashier (no email sent)
    "AdminSetUserPassword",  # cashier's first password, and owner's password reset
    "AdminAddUserToGroup",  # put the cashier in the `cashier` group
    "AdminDisableUser",  # owner disables a cashier
    "AdminEnableUser",  # ... and enables them again
    "AdminUserGlobalSignOut",  # end a disabled cashier's sessions / after a password reset
    "AdminDeleteUser",  # clean up a half-created cashier if setup fails
]  # Vite dev server; CloudFront URL is added in Step 6

# Inside the official Lambda build image (Linux arm64): install the pinned runtime deps, then copy our code
# into an `api/` package next to them. Handler = api.handler.handler.
BUNDLE_COMMAND = (
    "pip install --no-cache-dir --disable-pip-version-check -r requirements.txt -t /asset-output"
    " && mkdir -p /asset-output/api && cp -r . /asset-output/api/"
    " && rm -f /asset-output/api/requirements.txt"
)


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        table: dynamodb.ITable,
        user_pool: cognito.IUserPool,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        origins = self.node.try_get_context("corsOrigins") or DEFAULT_ORIGINS

        # --- Lambda -------------------------------------------------------------
        fn = lambda_.Function(
            self,
            "ApiFn",
            runtime=RUNTIME,
            architecture=lambda_.Architecture.ARM_64,
            handler="api.handler.handler",
            code=lambda_.Code.from_asset(
                str(API_DIR),
                exclude=["**/__pycache__", "*.pyc"],
                bundling=cdk.BundlingOptions(
                    image=RUNTIME.bundling_image,
                    platform="linux/arm64",
                    command=["bash", "-c", BUNDLE_COMMAND],
                ),
            ),
            memory_size=512,  # FastAPI + pydantic import time; more memory = more CPU = faster cold start
            timeout=Duration.seconds(10),
            environment={
                "TABLE_NAME": table.table_name,
                "USER_POOL_ID": user_pool.user_pool_id,
                "ALLOWED_ORIGINS": ",".join(origins),
                "ENABLE_DOCS": "0",
            },
            log_group=logs.LogGroup(
                self,
                "ApiFnLogs",
                retention=logs.RetentionDays.ONE_MONTH,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )
        table.grant_read_write_data(fn)
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[f"cognito-idp:{a}" for a in COGNITO_ADMIN_ACTIONS],
                resources=[user_pool.user_pool_arn],  # this pool only
            )
        )

        # --- API Gateway --------------------------------------------------------
        access_logs = logs.LogGroup(
            self,
            "ApiAccessLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.api = apigw.RestApi(
            self,
            "Api",
            rest_api_name="sumaat-api",
            endpoint_types=[apigw.EndpointType.REGIONAL],
            # Account-wide setting shared with other APIs in this account (e.g. HrApi): keep it on destroy.
            cloud_watch_role=True,
            cloud_watch_role_removal_policy=RemovalPolicy.RETAIN,
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=10,
                throttling_burst_limit=20,
                logging_level=apigw.MethodLoggingLevel.ERROR,
                data_trace_enabled=False,  # never log request/response bodies
                metrics_enabled=False,
                access_log_destination=apigw.LogGroupLogDestination(access_logs),
                access_log_format=apigw.AccessLogFormat.json_with_standard_fields(
                    caller=False,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=False,
                ),
            ),
            # Browser preflight (OPTIONS) answered here, without login.
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=origins,
                allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                allow_headers=["Authorization", "Content-Type"],
                max_age=Duration.hours(1),
            ),
        )

        # Let the browser read API Gateway's own errors (e.g. 401 from the authorizer, 429 throttled).
        for rtype, name in ((apigw.ResponseType.DEFAULT_4_XX, "Default4xx"), (apigw.ResponseType.DEFAULT_5_XX, "Default5xx")):
            self.api.add_gateway_response(
                name, type=rtype, response_headers={"Access-Control-Allow-Origin": "'*'"}
            )

        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "Authorizer", cognito_user_pools=[user_pool], authorizer_name="sumaat-users"
        )
        integration = apigw.LambdaIntegration(fn)
        login = {"authorizer": authorizer, "authorization_type": apigw.AuthorizationType.COGNITO}

        root = self.api.root
        public: list[apigw.Method] = []

        # Public browse (GET only).
        public.append(root.add_resource("health").add_method("GET", integration))
        public.append(root.add_resource("categories").add_method("GET", integration))
        restaurants = root.add_resource("restaurants")
        public.append(restaurants.add_method("GET", integration))
        restaurant = restaurants.add_resource("{id}")
        public.append(restaurant.add_method("GET", integration))

        # Everything else needs login. A specific GET beats ANY on the same resource.
        restaurants.add_method("ANY", integration, **login)  # POST /restaurants
        restaurant.add_method("ANY", integration, **login)  # PATCH /restaurants/{id}
        restaurant.add_resource("{proxy+}").add_method("ANY", integration, **login)  # menu routes
        root.add_resource("{proxy+}").add_method("ANY", integration, **login)  # orders (Step 5) and the rest

        CfnOutput(self, "ApiUrl", value=self.api.url)

        self._suppress_nag(public)

    def _suppress_nag(self, public: list[apigw.Method]) -> None:
        open_on_purpose = [
            {
                "id": "AwsSolutions-APIG4",
                "reason": "Public on purpose: browsing restaurants/menus/categories and the health check need no "
                "login; CORS preflight (OPTIONS) can never carry a token.",
            },
            {
                "id": "AwsSolutions-COG4",
                "reason": "Public on purpose: browse GETs and CORS preflight. All other methods use the Cognito "
                "user pool authorizer.",
            },
        ]
        for method in public + [m for m in self.api.methods if m.http_method == "OPTIONS"]:
            NagSuppressions.add_resource_suppressions(method, open_on_purpose)

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-APIG2",
                    "reason": "Request bodies are validated in the app by Pydantic (unknown fields rejected, "
                    "strict ints for money); a second copy of the schema in API Gateway would drift.",
                },
                {
                    "id": "AwsSolutions-APIG3",
                    "reason": "WAF costs more than a one-week POC justifies; stage throttling (10 req/s, burst 20) "
                    "limits abuse and cost instead.",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS-managed policies limited to logging: Lambda basic execution (CloudWatch Logs) "
                    "and API Gateway push-to-CloudWatch-Logs.",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs",
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "grant_read_write_data adds <table>/index/* so the API can query our own table's "
                    "GSIs (GEO lookup, order lists); no other tables.",
                    "appliesTo": [{"regex": "/^Resource::.*\\/index\\/\\*$/"}],
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Python 3.14 is pinned project-wide (.python-version) so local tests match the "
                    "Lambda runtime; upgrade together later.",
                },
            ],
        )
