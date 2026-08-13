#!/usr/bin/env py
import os
import importlib

import aws_cdk as cdk

from health_connector_cdk.health_connector_cdk_stack import MedicaidCdkStack


app = cdk.App()

# Select target environment:
#   cdk deploy -c env=dev
#   cdk deploy -c env=uat
#   cdk deploy -c env=prod
#   CDK_ENV=prod cdk deploy
# Falls back to 'dev' if neither is specified.
env_name = app.node.try_get_context('env') or os.getenv('CDK_ENV', 'dev')

config_module = importlib.import_module(f'config.{env_name}')
config = config_module.CONFIG

# Stack name encodes env + version so multiple stacks can coexist in the same account.
# To deploy a v2 alongside v1: bump version in config/{env}.py and re-run cdk deploy.
stack_name = f'MedicaidStack-{config.env}-{config.version}'

MedicaidCdkStack(
    app,
    stack_name,
    config=config,
    env=cdk.Environment(account=config.aws_account, region=config.aws_region),
)

app.synth()
