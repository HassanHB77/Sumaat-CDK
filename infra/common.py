"""App-wide settings shared by app.py and the tests."""

import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks

PROJECT_TAG = ("project", "sumaat")
REGION = "us-east-1"


def images_bucket_name(stack: cdk.Stack) -> str:
    """Restaurant/dish photos bucket. A FIXED name: SumaatWeb creates it (CloudFront /img/* with OAC) and SumaatApi,
    deployed earlier, only needs the name (env var + IAM). No cross-stack reference, so no dependency cycle."""
    return f"sumaat-images-{stack.account}-{stack.region}"


def apply_project_guards(app: cdk.App) -> None:
    """Tag every resource and run cdk-nag on the whole app."""
    cdk.Tags.of(app).add(*PROJECT_TAG)
    cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))
