"""App-wide settings shared by app.py and the tests."""

import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks

PROJECT_TAG = ("project", "sumaat")
REGION = "us-east-1"


def apply_project_guards(app: cdk.App) -> None:
    """Tag every resource and run cdk-nag on the whole app."""
    cdk.Tags.of(app).add(*PROJECT_TAG)
    cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))
