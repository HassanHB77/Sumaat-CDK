#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.agent_stack import AgentStack
from infra.api_stack import ApiStack
from infra.common import REGION, apply_project_guards
from infra.auth_stack import AuthStack
from infra.data_stack import DataStack
from infra.notify_stack import NotifyStack
from infra.web_stack import WebStack

app = cdk.App()
env = cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=REGION)

# Stacks, in deploy order.
data = DataStack(app, "SumaatData", env=env)
auth = AuthStack(app, "SumaatAuth", env=env)
api = ApiStack(app, "SumaatApi", table=data.table, user_pool=auth.user_pool, env=env)
agent = AgentStack(
    app, "SumaatAgent", table=data.table, user_pool=auth.user_pool, user_pool_client=auth.client, env=env
)
web = WebStack(
    app,
    "SumaatWeb",
    api=api.api,
    user_pool=auth.user_pool,
    user_pool_client=auth.client,
    agent_runtime_arn=agent.runtime_arn,
    env=env,
)
notify = NotifyStack(app, "SumaatNotify", table=data.table, site_domain=web.distribution.distribution_domain_name, env=env)

apply_project_guards(app)  # project=sumaat tag + cdk-nag on everything
app.synth()
