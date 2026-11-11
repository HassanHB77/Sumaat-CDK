import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Annotations, Match, Template

from infra.api_stack import ApiStack
from infra.auth_stack import AuthStack
from infra.common import apply_project_guards
from infra.data_stack import DataStack
from infra.web_stack import WEB_PLACEHOLDER, WebStack, site_source_dir

ENV = cdk.Environment(account="123456789012", region="us-east-1")


@pytest.fixture(scope="module")
def stack() -> WebStack:
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})  # no Docker in unit tests
    data = DataStack(app, "SumaatData", env=ENV)
    auth = AuthStack(app, "SumaatAuth", env=ENV)
    api = ApiStack(app, "SumaatApi", table=data.table, user_pool=auth.user_pool, env=ENV)
    web = WebStack(app, "SumaatWeb", api=api.api, user_pool=auth.user_pool, user_pool_client=auth.client, env=ENV)
    apply_project_guards(app)
    app.synth()
    return web


@pytest.fixture(scope="module")
def template(stack) -> Template:
    return Template.from_stack(stack)


def _dist(template) -> dict:
    (d,) = template.find_resources("AWS::CloudFront::Distribution").values()
    return d["Properties"]["DistributionConfig"]


def test_bucket_is_private_and_ssl_only(template):
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        },
    )
    template.has_resource_properties(
        "AWS::S3::BucketPolicy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [Match.object_like({"Effect": "Deny", "Condition": {"Bool": {"aws:SecureTransport": "false"}}})]
                )
            }
        },
    )


def test_cloudfront_reads_bucket_with_oac(template):
    template.resource_count_is("AWS::CloudFront::OriginAccessControl", 1)


def test_default_behavior_is_site(template):
    d = _dist(template)
    assert d["DefaultRootObject"] == "index.html"
    assert d["DefaultCacheBehavior"]["ViewerProtocolPolicy"] == "redirect-to-https"
    assert len(d["DefaultCacheBehavior"]["FunctionAssociations"]) == 1
    assert "CustomErrorResponses" not in d  # would turn real API 404s into the website


def test_api_behavior(template):
    (api,) = _dist(template)["CacheBehaviors"]
    assert api["PathPattern"] == "/api/*"
    assert api["ViewerProtocolPolicy"] == "redirect-to-https"
    assert set(api["AllowedMethods"]) == {"GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"}
    assert api["CachePolicyId"] == "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"  # Managed-CachingDisabled
    assert api["OriginRequestPolicyId"] == "b689b0a8-53d0-40ab-baf2-68738e2966ac"  # AllViewerExceptHostHeader
    assert len(api["FunctionAssociations"]) == 1


def test_api_origin_uses_prod_stage(template):
    origins = _dist(template)["Origins"]
    api_origin = next(o for o in origins if "CustomOriginConfig" in o)
    # CDK computes it at deploy time from the API URL (https://x.execute-api.../prod/): "/" + 4th part = "/prod".
    join = api_origin["OriginPath"]["Fn::Join"]
    assert join[1][0] == "/" and join[1][1]["Fn::Select"][0] == 3
    assert api_origin["CustomOriginConfig"]["OriginProtocolPolicy"] == "https-only"


def test_two_cloudfront_functions(template):
    template.resource_count_is("AWS::CloudFront::Function", 2)


def test_site_upload_invalidates_cache(template):
    template.has_resource_properties("Custom::CDKBucketDeployment", {"DistributionPaths": ["/*"]})


def test_cache_headers_split(template):
    deployments = [d["Properties"] for d in template.find_resources("Custom::CDKBucketDeployment").values()]
    assert len(deployments) == 2
    controls = sorted(d["SystemMetadata"]["cache-control"] for d in deployments)
    assert controls == ["no-cache", "public, max-age=31536000, immutable"]
    assert all(d["Prune"] is False for d in deployments)  # they share the bucket


def test_map_key_locked_down(template):
    (key,) = template.find_resources("AWS::Location::APIKey").values()
    p = key["Properties"]
    assert p["NoExpiry"] is True
    r = p["Restrictions"]
    assert r["AllowActions"] == ["geo-maps:GetTile", "geo-maps:GetStaticMap"]
    assert r["AllowResources"] == ["arn:aws:geo-maps:us-east-1::provider/default"]
    assert len(r["AllowReferers"]) == 2 and "http://localhost:5173/*" in r["AllowReferers"]


def test_map_key_value_read_with_least_privilege(template):
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [Match.object_like({"Action": "geo:DescribeKey", "Resource": Match.any_value()})]
                )
            }
        },
    )


def test_placeholder_until_react_build_exists():
    assert (WEB_PLACEHOLDER / "index.html").exists()
    assert site_source_dir().name in ("dist", "placeholder")


def test_site_url_output(template):
    assert "SiteUrl" in template.find_outputs("*")


def test_cdk_nag_clean(stack):
    errors = Annotations.from_stack(stack).find_error("*", Match.string_like_regexp("AwsSolutions-.*"))
    assert errors == [], errors
