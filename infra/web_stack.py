"""WebStack: the website (S3 + CloudFront), with /api/* forwarded to the API on the same address.

    Browser --https--> CloudFront (https://dxxxx.cloudfront.net)
                         |-- /api/*  --> API Gateway stage /prod   (no caching, Authorization passed through)
                         '-- /*      --> private S3 bucket         (the React build, or a placeholder page)

One address for site + API = no CORS in production, and the frontend calls the relative path "/api".

The app reads /config.json at startup (Cognito ids, region, map key), written here from the other stacks,
so nobody copies ids by hand. index.html + config.json are never cached; /assets/* (hashed names) are cached
for a year.
"""

from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_iam as iam
from aws_cdk import aws_location as location
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import custom_resources as cr
from cdk_nag import NagSuppressions
from constructs import Construct

ROOT = Path(__file__).resolve().parent.parent
FUNCTIONS = Path(__file__).resolve().parent / "cf_functions"
WEB_DIST = ROOT / "web" / "dist"  # the React build (Step 7)
WEB_PLACEHOLDER = ROOT / "web" / "placeholder"  # until then
DEV_ORIGIN = "http://localhost:5173"  # Vite dev server (map key referer)
NO_CACHE = [s3deploy.CacheControl.no_cache()]
LONG_CACHE = [s3deploy.CacheControl.from_string("public, max-age=31536000, immutable")]


def site_source_dir() -> Path:
    """Upload the real build when it exists, otherwise the placeholder page."""
    return WEB_DIST if (WEB_DIST / "index.html").exists() else WEB_PLACEHOLDER


class WebStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        api: apigw.RestApi,
        user_pool: cognito.IUserPool,
        user_pool_client: cognito.IUserPoolClient,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self,
            "SiteBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,  # only CloudFront can read it (OAC)
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,  # POC: `cdk destroy` empties and removes it
        )

        def fn(construct_id: str, file: str) -> cloudfront.Function:
            return cloudfront.Function(
                self,
                construct_id,
                code=cloudfront.FunctionCode.from_file(file_path=str(FUNCTIONS / file)),
                runtime=cloudfront.FunctionRuntime.JS_2_0,
            )

        self.distribution = cloudfront.Distribution(
            self,
            "Site",
            comment="Sumaat website + /api",
            default_root_object="index.html",
            price_class=cloudfront.PriceClass.PRICE_CLASS_ALL,  # includes Middle East edge locations
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=fn("SpaIndexFn", "spa_index.js"),
                        event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                    )
                ],
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.RestApiOrigin(api),  # origin path = /prod (the stage)
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,  # live data, never cached
                    # Passes every viewer header (incl. Authorization) and the query string, except Host
                    # (API Gateway needs its own Host).
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                    function_associations=[
                        cloudfront.FunctionAssociation(
                            function=fn("StripApiPrefixFn", "strip_api_prefix.js"),
                            event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                        )
                    ],
                ),
            },
        )

        site_url = f"https://{self.distribution.distribution_domain_name}"
        map_key = self._map_key(site_url)

        # 1) Hashed build files (/assets/*): cached for a year; their names change on every build.
        assets = s3deploy.BucketDeployment(
            self,
            "DeployAssets",
            sources=[s3deploy.Source.asset(str(site_source_dir()))],
            include=["assets/*"],
            exclude=["*"],
            destination_bucket=bucket,
            cache_control=LONG_CACHE,
            prune=False,  # two deployments share the bucket; don't delete each other's files
        )
        # 2) Everything else (index.html, favicon ...) + the generated config.json: never cached, so a
        #    deploy is visible at once. Runs after the assets so a new index.html never points to missing files.
        pages = s3deploy.BucketDeployment(
            self,
            "DeploySite",
            sources=[
                s3deploy.Source.asset(str(site_source_dir()), exclude=["assets/*"]),
                s3deploy.Source.json_data(
                    "config.json",
                    {
                        "region": self.region,
                        "userPoolId": user_pool.user_pool_id,
                        "userPoolClientId": user_pool_client.user_pool_client_id,
                        "locationApiKey": map_key,
                        "apiBase": "/api",
                    },
                ),
            ],
            destination_bucket=bucket,
            cache_control=NO_CACHE,
            prune=False,
            distribution=self.distribution,
            distribution_paths=["/*"],  # refresh CloudFront after every upload
        )
        pages.node.add_dependency(assets)

        CfnOutput(self, "SiteUrl", value=site_url)

        self._suppress_nag()

    def _map_key(self, site_url: str) -> str:
        """Amazon Location (Maps v2) API key for the browser map, and its value for config.json.

        The key is public by design (it ships to every browser), so it is locked down: map tiles only,
        and only from our site and the local dev server.
        """
        key = location.CfnAPIKey(
            self,
            "MapKey",
            key_name="sumaat-web-maps",
            description="Browser map tiles for the Sumaat website",
            no_expiry=True,
            restrictions=location.CfnAPIKey.ApiKeyRestrictionsProperty(
                allow_actions=["geo-maps:GetTile", "geo-maps:GetStaticMap"],
                allow_resources=[f"arn:aws:geo-maps:{self.region}::provider/default"],
                allow_referers=[f"{site_url}/*", f"{DEV_ORIGIN}/*"],
            ),
        )
        # CloudFormation can't return the key's value, so read it once with an SDK call at deploy time.
        describe = cr.AwsSdkCall(
            service="Location",
            action="describeKey",
            parameters={"KeyName": key.key_name},
            physical_resource_id=cr.PhysicalResourceId.of(key.key_name),
            logging=cr.Logging.with_data_hidden(),  # don't write the key into CloudWatch
        )
        value = cr.AwsCustomResource(
            self,
            "MapKeyValue",
            on_create=describe,
            on_update=describe,
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [iam.PolicyStatement(actions=["geo:DescribeKey"], resources=[key.attr_key_arn])]
            ),
            install_latest_aws_sdk=False,
            timeout=Duration.minutes(2),
        )
        value.node.add_dependency(key)
        return value.get_response_field("Key")

    def _suppress_nag(self) -> None:
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-S1",
                    "reason": "POC: no S3 server access logs for the static site bucket; CloudFront and API "
                    "Gateway metrics cover the demo.",
                },
                {
                    "id": "AwsSolutions-CFR1",
                    "reason": "No geo restriction: demo audience (Saudi users and facilitators) may be anywhere.",
                },
                {
                    "id": "AwsSolutions-CFR2",
                    "reason": "WAF costs more than a one-week POC justifies; API Gateway stage throttling "
                    "(10 req/s, burst 20) still protects the API behind /api/*.",
                },
                {
                    "id": "AwsSolutions-CFR3",
                    "reason": "POC: CloudFront access logs not enabled; API Gateway access logs record API calls.",
                },
                {
                    "id": "AwsSolutions-CFR4",
                    "reason": "The default *.cloudfront.net certificate can't set a minimum TLS version; revisit "
                    "when a custom domain + ACM certificate are added.",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "CDK-managed helper Lambdas (bucket upload, auto-delete objects, map key lookup) use "
                    "the AWS-managed basic execution role (CloudWatch Logs only).",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CDK BucketDeployment helper needs wildcard object actions on the CDK asset bucket and "
                    "on this site bucket only, plus a CloudFront invalidation.",
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Runtime of CDK-managed helper Lambdas (BucketDeployment, auto-delete, "
                    "AwsCustomResource) is chosen by the CDK library.",
                },
            ],
        )
