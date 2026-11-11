"""WebStack: the website (S3 + CloudFront), with /api/* forwarded to the API on the same address.

    Browser --https--> CloudFront (https://dxxxx.cloudfront.net)
                         |-- /api/*  --> API Gateway stage /prod   (no caching, Authorization passed through)
                         '-- /*      --> private S3 bucket         (the React build, or a placeholder page)

One address for site + API = no CORS in production, and the frontend calls the relative path "/api".
"""

from pathlib import Path

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from cdk_nag import NagSuppressions
from constructs import Construct

ROOT = Path(__file__).resolve().parent.parent
FUNCTIONS = Path(__file__).resolve().parent / "cf_functions"
WEB_DIST = ROOT / "web" / "dist"  # the React build (Step 7)
WEB_PLACEHOLDER = ROOT / "web" / "placeholder"  # until then


def site_source_dir() -> Path:
    """Upload the real build when it exists, otherwise the placeholder page."""
    return WEB_DIST if (WEB_DIST / "index.html").exists() else WEB_PLACEHOLDER


class WebStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, api: apigw.RestApi, **kwargs) -> None:
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

        s3deploy.BucketDeployment(
            self,
            "DeploySite",
            sources=[s3deploy.Source.asset(str(site_source_dir()))],
            destination_bucket=bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],  # refresh CloudFront after every upload
        )

        CfnOutput(self, "SiteUrl", value=f"https://{self.distribution.distribution_domain_name}")

        self._suppress_nag()

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
                    "reason": "CDK-managed helper Lambdas (bucket upload, auto-delete objects) use the AWS-managed "
                    "basic execution role (CloudWatch Logs only).",
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
                    "reason": "Runtime of CDK-managed helper Lambdas (BucketDeployment, auto-delete) is chosen by "
                    "the CDK library.",
                },
            ],
        )
