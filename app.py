#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.api_stack import ApiStack
from infra.common import REGION, apply_project_guards
from infra.auth_stack import AuthStack
from infra.data_stack import DataStack

app = cdk.App()
env = cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=REGION)

# Stacks, in deploy order.
data = DataStack(app, "SumaatData", env=env)
auth = AuthStack(app, "SumaatAuth", env=env)
api = ApiStack(app, "SumaatApi", table=data.table, user_pool=auth.user_pool, env=env)

apply_project_guards(app)  # project=sumaat tag + cdk-nag on everything
app.synth()
