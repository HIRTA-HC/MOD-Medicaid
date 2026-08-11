from .base_config import StackConfig

# Copy this file to config/dev.py and fill in the values for your dev environment.
# config/dev.py is gitignored — never commit it with real account IDs.

CONFIG = StackConfig(
    env='dev',
    version='v1',
    aws_account='YOUR_AWS_ACCOUNT_ID',       # 12-digit AWS account number
    aws_region='ap-south-1',                 # change if deploying to a different region
    secrets_name='dev_middleware_credentials', # Secrets Manager secret name CDK will create

    # Lyft credentials — optional at deploy time; fill in via TMS Settings page after deploy
    lyft_client_id='',
    lyft_client_secret='',
    lyft_program_id='',
    # lyft_auth_url and lyft_api_url use the defaults from StackConfig
)
