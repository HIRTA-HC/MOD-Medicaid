from dataclasses import dataclass


@dataclass
class StackConfig:
    env: str          # 'dev' | 'uat' | 'prod'
    version: str      # 'v1' | 'v2' etc.
    aws_account: str
    aws_region: str
    secrets_name: str  # Secrets Manager secret name — created and populated by the stack

    # Via credentials — stored in Secrets Manager, populated by the stack on deploy
    via_client_id: str = ''
    via_client_secret: str = ''
    via_api_key: str = ''
    via_auth_url: str = 'https://trip-api.auth.us-east-1.amazoncognito.com/oauth2/token'
    via_api_url: str = 'us-east-1.trip-api.ridewithvia.com'

    # Lyft credentials — stored in Secrets Manager, populated by the stack on deploy
    lyft_client_id: str = ''
    lyft_client_secret: str = ''
    lyft_program_id: str = ''
    lyft_auth_url: str = 'https://api.lyft.com/oauth/token'
    lyft_api_url: str = 'https://api.lyft.com/v1/tapi/atms/webhooks'

    # Optional — only required when deploying the full stack with custom domain
    domain_name: str = ''
    certificate_arn: str = ''                    # us-west-1 cert ARN
    us_east_1_certificate_arn: str = ''          # us-east-1 cert ARN (CloudFront)
    cognito_domain_prefix: str = ''              # overrides auto-generated prefix

    def res(self, resource_name: str) -> str:
        """Return Middleware_{env}_{resource_name}_{version} — used for AWS resource names."""
        return f'Middleware_{self.env}_{resource_name}_{self.version}'

    def res_lower(self, resource_name: str) -> str:
        """Lowercase + hyphenated variant for S3 bucket names."""
        return self.res(resource_name).lower().replace('_', '-')

    def construct_id(self, base: str) -> str:
        """Return a CDK construct ID that includes env+version for console clarity."""
        return f'{base}-{self.env}-{self.version}'
