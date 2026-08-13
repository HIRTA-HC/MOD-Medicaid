from .base_config import StackConfig

# Copy this file to config/uat.py and fill in the values for your UAT environment.
# config/uat.py is gitignored — never commit it with real account IDs or ARNs.

CONFIG = StackConfig(
    env='uat',
    version='v1',
    aws_account='YOUR_AWS_ACCOUNT_ID',       # 12-digit AWS account number
    aws_region='us-west-1',                  # change if deploying to a different region
    secrets_name='uat_credentials',           # Secrets Manager secret name CDK will create

    # Via credentials — optional at deploy time; fill in via TMS Settings page after deploy
    via_client_id='',
    via_client_secret='',
    via_api_key='',
    # via_auth_url and via_api_url use the defaults from StackConfig

    # Lyft credentials — optional at deploy time; fill in via TMS Settings page after deploy
    lyft_client_id='',
    lyft_client_secret='',
    lyft_program_id='',
    # lyft_auth_url and lyft_api_url use the defaults from StackConfig
)
