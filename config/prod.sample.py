from .base_config import StackConfig

# Copy this file to config/prod.py and fill in the values for your production environment.
# config/prod.py is gitignored — never commit it with real account IDs, ARNs, or domain info.

CONFIG = StackConfig(
    env='prod',
    version='v1',
    aws_account='YOUR_AWS_ACCOUNT_ID',       # 12-digit AWS account number
    aws_region='us-west-1',                  # change if deploying to a different region
    secrets_name='prod_credentials',          # Secrets Manager secret name CDK will create

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

    # Custom domain — required if you want HTTPS on a custom domain
    domain_name='YOUR_DOMAIN_NAME',                     # e.g. healthconnector.example.org
    certificate_arn='YOUR_US_WEST_1_ACM_CERT_ARN',      # ACM cert in us-west-1 for CloudFront origin
    us_east_1_certificate_arn='YOUR_US_EAST_1_ACM_CERT_ARN', # ACM cert in us-east-1 (required by CloudFront)
    cognito_domain_prefix='health-connector-prod-v1',   # must be globally unique
)
