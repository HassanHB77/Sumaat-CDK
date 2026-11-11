#!/usr/bin/env python3
import os
import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks

app = cdk.App()
env = cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region="us-east-1")

# Stacks are added here, in deploy order.

cdk.Tags.of(app).add("project", "sumaat")              # cost tag on every resource
cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))  # cdk-nag from day one
app.synth()