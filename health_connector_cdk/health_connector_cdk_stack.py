from aws_cdk import (
    BundlingOptions,
    CfnOutput,
    Duration,
    RemovalPolicy,
    SecretValue,
    Stack,
    aws_apigateway as apigw_,
    aws_lambda as lambda_,
    aws_cognito as cognito_,
    aws_dynamodb as dynamodb_,
    aws_s3 as s3_,
    aws_s3_deployment as s3_deployment_,
    aws_route53 as route53_,
    aws_route53_targets as route53_targets_,
    aws_certificatemanager as acm_,
    aws_cloudfront as cloudfront_,
    aws_cloudfront_origins as origins_,
    aws_secretsmanager as secretsmanager
)
from constructs import Construct

from config.base_config import StackConfig


class ApiScope():
    def __init__(self, api_scope: cognito_.ResourceServerScope, resource_server: cognito_.UserPoolResourceServer, resource_server_identifier: str):
        self.api_scope = api_scope
        self.resource_server = resource_server
        self.resource_server_identifier = resource_server_identifier
        self.auth_scope = f'{resource_server_identifier}/{api_scope.scope_name}'


class MedicaidCdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, config: StackConfig, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.config = config

        # 1. S3 bucket created first so it exists before any other resource references it
        frontend_bucket = self.create_frontend_bucket()

        # 2. Shared / foundational resources
        secret  = self.create_secrets()
        table   = self.create_mod_medicaid_table()
        table2  = self.create_mod_medicaid_history_table()
        # hosted_zone                         = self.create_hosted_zone()
        # certificate, us_east_1_certificate  = self.create_certificates(hosted_zone)

        # 3. Lambda functions
        api_handler       = self.create_api_handler_lambda(table, table2, secret)
        # dashboard_handler = self.create_dashboard_handler_lambda(table)
        # kiosk_workerbee   = self.create_kiosk_workerbee_lambda(secret)
        # kiosk_statusbee   = self.create_kiosk_statusbee_lambda(secret)
        # lyft_tapi_trips   = self.create_lyft_tapi_trips_lambda(table)

        # Cognito user pool + web client for frontend login
        user_pool, _  = self.create_cognito_user_pool()
        web_client     = self.create_web_app_client(user_pool)
        CfnOutput(self, 'UserPoolId',       value=user_pool.user_pool_id,            description='Cognito User Pool ID')
        CfnOutput(self, 'UserPoolClientId', value=web_client.user_pool_client_id,    description='Cognito Web App Client ID')

        # 4. API Gateway — pass user_pool to wire Cognito authorizer
        api, authorizer = self.create_api_gateway(user_pool=user_pool)

        # 5. CloudFront distribution — wires S3 bucket + API Gateway origins
        distribution = self.create_website_hosting(api, frontend_bucket)

        # 6. API route groups — comment out any line to drop those endpoints
        # self.create_oauth2_endpoint(api, user_pool_domain)
        self.create_mod_medicaid_endpoints(api, authorizer, None, api_handler)
        # self.create_kiosk_deprecated_endpoints(api, authorizer, kiosk_workerbee, kiosk_statusbee)
        # self.create_kiosk_endpoints(api, authorizer, api_handler)
        self.create_via_webhook_endpoint(api, api_handler)
        # self.create_dashboard_endpoint(api, authorizer, dashboard_handler)

        # 7. React assets are uploaded separately after deploy — see deploy_frontend.ps1


    # ── SECRETS ────────────────────────────────────────────────────────────────

    def create_secrets(self) -> secretsmanager.Secret:
        """Create the Secrets Manager secret and populate it from config values.
        NOTE: if a secret with this name already exists in AWS, delete it first
        (or rename secrets_name in config) before deploying — CloudFormation will
        error on a name collision.
        """
        return secretsmanager.Secret(
            self,
            self.config.construct_id('MedicaidCredentials'),
            secret_name=self.config.secrets_name,
            description=f'Via and Lyft credentials for {self.config.env} {self.config.version}',
            secret_object_value={
                # TMS settings — single source of truth for Via credentials
                'tms_provider':         SecretValue.unsafe_plain_text(''),
                'tms_agency_name':      SecretValue.unsafe_plain_text(''),
                'tms_api_base_url':     SecretValue.unsafe_plain_text(self.config.via_api_url),
                'tms_service_tag':      SecretValue.unsafe_plain_text(''),
                'tms_client_id':        SecretValue.unsafe_plain_text(self.config.via_client_id),
                'tms_client_secret':    SecretValue.unsafe_plain_text(self.config.via_client_secret),
                'tms_api_key':          SecretValue.unsafe_plain_text(self.config.via_api_key),
                'tms_token_url':        SecretValue.unsafe_plain_text(self.config.via_auth_url),
                'tms_auto_book':        SecretValue.unsafe_plain_text(''),
                'tms_timezone':         SecretValue.unsafe_plain_text(''),
                'tms_rider_lookup':     SecretValue.unsafe_plain_text(''),
                'tms_webhook_endpoint': SecretValue.unsafe_plain_text(''),
                'via_hmac_key':         SecretValue.unsafe_plain_text(''),
                # Lyft credentials — unchanged
                'lyft_client_id':     SecretValue.unsafe_plain_text(self.config.lyft_client_id),
                'lyft_client_secret': SecretValue.unsafe_plain_text(self.config.lyft_client_secret),
                'lyft_program_id':    SecretValue.unsafe_plain_text(self.config.lyft_program_id),
                'lyft_auth_url':      SecretValue.unsafe_plain_text(self.config.lyft_auth_url),
                'lyft_api_url':       SecretValue.unsafe_plain_text(self.config.lyft_api_url),
            }
        )


    # ── DYNAMODB ───────────────────────────────────────────────────────────────

    def create_mod_medicaid_table(self) -> dynamodb_.TableV2:
        return dynamodb_.TableV2(
            self,
            self.config.construct_id('MODMedicaidTable'),
            table_name=self.config.res('MOD_Medicaid'),
            contributor_insights=True,
            billing=dynamodb_.Billing.on_demand(),
            point_in_time_recovery=True,
            partition_key=dynamodb_.Attribute(
                name='atms_ride_id',
                type=dynamodb_.AttributeType.STRING
            )
        )

    def create_mod_medicaid_history_table(self) -> dynamodb_.TableV2:
        return dynamodb_.TableV2(
            self,
            self.config.construct_id('MODMedicaidHistoryTable'),
            table_name=self.config.res('MOD_Medicaid_History'),
            contributor_insights=True,
            billing=dynamodb_.Billing.on_demand(),
            point_in_time_recovery=True,
            partition_key=dynamodb_.Attribute(
                name='atms_ride_id',
                type=dynamodb_.AttributeType.STRING
            ),
            global_secondary_indexes=[dynamodb_.GlobalSecondaryIndexPropsV2(
                index_name='g111',
                partition_key=dynamodb_.Attribute(
                    name='update_time',
                    type=dynamodb_.AttributeType.STRING
                ),
            )],
        )


    # ── LAMBDA FUNCTIONS ───────────────────────────────────────────────────────

    def create_api_handler_lambda(self, table: dynamodb_.TableV2, table2: dynamodb_.TableV2, secret: secretsmanager.Secret) -> lambda_.Function:
        api_handler = lambda_.Function(
            self,
            self.config.construct_id('MedicaidApiHandler'),
            function_name=self.config.res('MedicaidApiHandler'),
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset('lambda',
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=["bash", "-c", "pip install -r requirements.txt -t /asset-output && rsync -r . /asset-output"]
                )
            ),
            handler='health_connector.api_handler',
            timeout=Duration.minutes(1),
            environment={
                'TABLE_NAME':         self.config.res('MOD_Medicaid'),
                'HISTORY_TABLE_NAME': self.config.res('MOD_Medicaid_History'),
                'SECRETS_NAME':       self.config.secrets_name,
                'Execution':          'On_AWS'
            }
        )
        secret.grant_read(api_handler.role)
        secret.grant_write(api_handler.role)
        table.grant_read_write_data(api_handler)
        table2.grant_read_write_data(api_handler)
        return api_handler

    def create_dashboard_handler_lambda(self, table: dynamodb_.TableV2) -> lambda_.Function:
        dashboard_handler = lambda_.Function(
            self,
            self.config.construct_id('DashboardHandler'),
            function_name=self.config.res('DashboardHandler'),
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset('lambda'),
            handler='health_connector.dashboard_handler',
            environment={
                'TABLE_NAME': self.config.res('MOD_Medicaid')
            }
        )
        table.grant_read_data(dashboard_handler)
        return dashboard_handler

    def create_kiosk_workerbee_lambda(self, secret: secretsmanager.Secret) -> lambda_.Function:
        kiosk_workerbee = lambda_.Function(
            self,
            self.config.construct_id('KioskWorker'),
            function_name=self.config.res('KioskWorker'),
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset('lambda',
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=["bash", "-c", "pip install -r requirements.txt -t /asset-output && rsync -r . /asset-output"]
                )
            ),
            handler='health_connector.lambda_kiosk',
            timeout=Duration.minutes(10),
            environment={
                'TABLE_NAME':   self.config.res('MOD_Medicaid'),
                'SECRETS_NAME': self.config.secrets_name,
                'Execution':    'On_AWS'
            }
        )
        secret.grant_read(kiosk_workerbee.role)
        return kiosk_workerbee

    def create_kiosk_statusbee_lambda(self, secret: secretsmanager.Secret) -> lambda_.Function:
        kiosk_statusbee = lambda_.Function(
            self,
            self.config.construct_id('KioskStatus'),
            function_name=self.config.res('KioskStatus'),
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset('lambda',
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=["bash", "-c", "pip install -r requirements.txt -t /asset-output && rsync -r . /asset-output"]
                )
            ),
            handler='health_connector.lambda_kiosk_status',
            timeout=Duration.minutes(10),
            environment={
                'TABLE_NAME':   self.config.res('MOD_Medicaid'),
                'SECRETS_NAME': self.config.secrets_name,
                'Execution':    'On_AWS'
            }
        )
        secret.grant_read(kiosk_statusbee.role)
        return kiosk_statusbee

    def create_lyft_tapi_trips_lambda(self, table: dynamodb_.TableV2) -> lambda_.Function:
        lyft_tapi_trips = lambda_.Function(
            self,
            self.config.construct_id('LyftTAPITrips'),
            function_name=self.config.res('LyftTAPITrips'),
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset('lambda',
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=["bash", "-c", "pip install -r requirements.txt -t /asset-output && rsync -r . /asset-output"]
                )
            ),
            handler='health_connector.lambda_lyft_tapi_trips_v1',
            timeout=Duration.minutes(10),
            environment={
                'TABLE_NAME': self.config.res('MOD_Medicaid')
            }
        )
        table.grant_read_write_data(lyft_tapi_trips)
        return lyft_tapi_trips


    # ── DNS & CERTIFICATES ─────────────────────────────────────────────────────

    def create_hosted_zone(self) -> route53_.IHostedZone:
        return route53_.HostedZone.from_lookup(
            self,
            self.config.construct_id('HostedZone'),
            domain_name=self.config.domain_name
        )

    def create_certificates(self, hosted_zone: route53_.IHostedZone) -> tuple[acm_.ICertificate, acm_.ICertificate]:
        us_east_1_certificate = acm_.Certificate.from_certificate_arn(
            self,
            self.config.construct_id('CertificateUsEast1'),
            certificate_arn=self.config.us_east_1_certificate_arn
        )
        certificate = acm_.Certificate(
            self,
            self.config.construct_id('Certificate'),
            domain_name=self.config.domain_name,
            subject_alternative_names=[f'*.{self.config.domain_name}'],
            validation=acm_.CertificateValidation.from_dns(hosted_zone)
        )
        return certificate, us_east_1_certificate


    # ── COGNITO ───────────────────────────────────────────────────────────────

    def create_cognito_user_pool(self) -> tuple[cognito_.UserPool, cognito_.UserPoolDomain]:
        user_pool = cognito_.UserPool(
            self,
            self.config.construct_id('UserPool'),
            account_recovery=cognito_.AccountRecovery.EMAIL_ONLY,
            auto_verify=cognito_.AutoVerifiedAttrs(email=False),
            user_pool_name=self.config.res('UserPool'),
            self_sign_up_enabled=False,
            sign_in_aliases=cognito_.SignInAliases(email=True),
            user_invitation=cognito_.UserInvitationConfig(
                email_subject='Health Connector Invitation',
                email_body='Your username is {username} and temporary password is {####}'
            )
        )
        domain_prefix = (
            self.config.cognito_domain_prefix
            or f'health-connector-{self.config.env}-{self.config.version}'
        )
        user_pool_domain = cognito_.UserPoolDomain(
            self,
            self.config.construct_id('UserPoolDomain'),
            user_pool=user_pool,
            cognito_domain=cognito_.CognitoDomainOptions(domain_prefix=domain_prefix)
        )
        return user_pool, user_pool_domain

    def create_cognito_api_scope(self, user_pool: cognito_.UserPool) -> ApiScope:
        api_scope = cognito_.ResourceServerScope(
            scope_name='health_connector',
            scope_description='Health Connector API access'
        )
        resource_server_identifier = self.config.res('api')
        resource_server = cognito_.UserPoolResourceServer(
            self,
            self.config.construct_id('ResourceServer'),
            user_pool=user_pool,
            identifier=resource_server_identifier,
            scopes=[api_scope]
        )
        return ApiScope(
            api_scope=api_scope,
            resource_server=resource_server,
            resource_server_identifier=resource_server_identifier
        )

    def create_cognito_api_clients(self, user_pool: cognito_.UserPool, api_scope: ApiScope) -> None:
        self.create_cognito_api_client(user_pool, api_scope, 'Lyft')
        self.create_cognito_api_client(user_pool, api_scope, 'Pompano')
        self.create_cognito_api_client(user_pool, api_scope, 'Via')

    def create_cognito_api_client(self, user_pool: cognito_.UserPool, api_scope: ApiScope, client: str) -> cognito_.UserPoolClient:
        return cognito_.UserPoolClient(
            self,
            self.config.construct_id(f'UserPoolApiClient-{client}'),
            user_pool=user_pool,
            user_pool_client_name=self.config.res(f'ApiClient_{client}'),
            generate_secret=True,
            o_auth=cognito_.OAuthSettings(
                flows=cognito_.OAuthFlows(client_credentials=True),
                scopes=[
                    cognito_.OAuthScope.resource_server(
                        server=api_scope.resource_server,
                        scope=api_scope.api_scope
                    )
                ]
            )
        )

    def create_cognito_web_client(self, user_pool: cognito_.UserPool, callback_url1: str, callback_url2: str) -> cognito_.UserPoolClient:
        return cognito_.UserPoolClient(
            self,
            self.config.construct_id('UserPoolWebClient'),
            user_pool=user_pool,
            user_pool_client_name=self.config.res('WebClient'),
            auth_session_validity=Duration.minutes(3),
            refresh_token_validity=Duration.minutes(8 * 24 * 60),   # 8 days
            access_token_validity=Duration.minutes(1 * 24 * 60),    # 1 day
            id_token_validity=Duration.minutes(1 * 24 * 60),        # 1 day
            auth_flows=cognito_.AuthFlow(user_password=True),
            o_auth=cognito_.OAuthSettings(
                flows=cognito_.OAuthFlows(
                    implicit_code_grant=True,
                    authorization_code_grant=True
                ),
                scopes=[cognito_.OAuthScope.OPENID, cognito_.OAuthScope.EMAIL],
                callback_urls=[callback_url1, callback_url2],
                logout_urls=[callback_url1]
            ),
            supported_identity_providers=[cognito_.UserPoolClientIdentityProvider.COGNITO]
        )

    def create_web_app_client(self, user_pool: cognito_.UserPool) -> cognito_.UserPoolClient:
        return cognito_.UserPoolClient(
            self,
            self.config.construct_id('WebAppClient'),
            user_pool=user_pool,
            user_pool_client_name=self.config.res('WebAppClient'),
            generate_secret=False,
            auth_flows=cognito_.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            prevent_user_existence_errors=True,
        )


    # ── WEBSITE HOSTING ────────────────────────────────────────────────────────

    def create_frontend_bucket(self) -> s3_.Bucket:
        """Create the public S3 static-website bucket. Called first in __init__
        so the bucket resource is defined before any other construct references it."""
        return s3_.Bucket(
            self,
            self.config.construct_id('MedicaidFrontendBucket'),
            bucket_name=f'medicaid-{self.config.env}-middlewarefrontend-{self.config.version}',
            website_index_document='index.html',
            website_error_document='index.html',
            public_read_access=True,
            removal_policy=RemovalPolicy.RETAIN,
            block_public_access=s3_.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False,
            ),
        )

    def create_website_hosting(self, api: apigw_.RestApi, bucket: s3_.Bucket) -> cloudfront_.Distribution:
        """Create the CloudFront distribution that serves the React app from S3
        and proxies API calls to API Gateway."""
        # S3 website endpoint — HTTP only at origin; CloudFront adds HTTPS.
        # bucket_website_domain_name gives the correct regional format
        # (some regions use a dot, others a hyphen, before the region name).
        s3_origin = origins_.HttpOrigin(
            bucket.bucket_website_domain_name,
            protocol_policy=cloudfront_.OriginProtocolPolicy.HTTP_ONLY,
        )

        # CloudFront prepends /prod so Lambda receives the correct path:
        #   /demo_ingestion → execute-api…/prod/demo_ingestion
        api_origin = origins_.HttpOrigin(
            f'{api.rest_api_id}.execute-api.{self.region}.amazonaws.com',
            origin_path='/prod',
            protocol_policy=cloudfront_.OriginProtocolPolicy.HTTPS_ONLY,
        )

        api_behavior = cloudfront_.BehaviorOptions(
            origin=api_origin,
            allowed_methods=cloudfront_.AllowedMethods.ALLOW_ALL,
            cache_policy=cloudfront_.CachePolicy.CACHING_DISABLED,
            origin_request_policy=cloudfront_.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            viewer_protocol_policy=cloudfront_.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        )

        distribution = cloudfront_.Distribution(
            self,
            self.config.construct_id('MedicaidFrontendCDF'),
            comment=f'Medicaid_{self.config.env}_Frontend_{self.config.version}',
            default_behavior=cloudfront_.BehaviorOptions(
                origin=s3_origin,
                # allowed_methods=cloudfront_.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cache_policy=cloudfront_.CachePolicy.CACHING_DISABLED,
                viewer_protocol_policy=cloudfront_.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                origin_request_policy=cloudfront_.OriginRequestPolicy.CORS_S3_ORIGIN,
                # cache_policy=cloudfront_.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
            ),
            additional_behaviors={
                '/demo_ingestion': api_behavior,
                '/via_webhook':    api_behavior,
                '/tms_settings':   api_behavior,
                '/dashboard':      api_behavior,
            },
            error_responses=[
                cloudfront_.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path='/index.html',
                    ttl=Duration.seconds(0),
                ),
                cloudfront_.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path='/index.html',
                    ttl=Duration.seconds(0),
                ),
            ],
        )

        CfnOutput(
            self,
            'CloudFrontURL',
            value=f'https://{distribution.distribution_domain_name}',
            description='Frontend CloudFront URL — use as the app base URL',
        )

        return distribution

    def deploy_frontend_assets(self, bucket: s3_.Bucket, distribution: cloudfront_.Distribution) -> None:
        """Copy middleware/dist to S3. CloudFront invalidation is done separately
        after deploy to avoid EarlyValidation failures when the distribution is
        created in the same stack."""
        s3_deployment_.BucketDeployment(
            self,
            self.config.construct_id('MedicaidFrontendDeployment'),
            sources=[s3_deployment_.Source.asset('middleware/dist')],
            destination_bucket=bucket,
            cache_control=[s3_deployment_.CacheControl.no_cache()],
        )

        CfnOutput(
            self,
            'InvalidationCommand',
            value=(
                f'aws cloudfront create-invalidation'
                f' --distribution-id {distribution.distribution_id}'
                f' --paths "/*"'
            ),
            description='Run this after deploy to invalidate the CloudFront cache',
        )


    # ── API GATEWAY ────────────────────────────────────────────────────────────

    def create_api_gateway(self, hosted_zone=None, certificate=None, user_pool=None):
        domain_kwargs = {}
        if certificate:
            domain_kwargs['domain_name'] = apigw_.DomainNameOptions(
                domain_name=f'api.{self.config.domain_name}',
                certificate=certificate,
                endpoint_type=apigw_.EndpointType.REGIONAL
            )

        api = apigw_.RestApi(
            self,
            self.config.construct_id('Api'),
            default_cors_preflight_options=apigw_.CorsOptions(
                allow_origins=apigw_.Cors.ALL_ORIGINS,
                allow_methods=apigw_.Cors.ALL_METHODS,
                allow_headers=['Content-Type', 'Authorization', 'X-Api-Key', 'X-Amz-Security-Token'],
            ),
            rest_api_name=self.config.res('api'),
            deploy=True,
            deploy_options=apigw_.StageOptions(
                stage_name='prod',
                metrics_enabled=True,
            ),
            **domain_kwargs
        )

        if hosted_zone:
            route53_.ARecord(
                self,
                self.config.construct_id('ApiARecord'),
                zone=hosted_zone,
                record_name='api',
                target=route53_.RecordTarget.from_alias(
                    route53_targets_.ApiGateway(api)
                )
            )

        authorizer = None
        if user_pool:
            authorizer = apigw_.CognitoUserPoolsAuthorizer(
                self,
                self.config.construct_id('Authorizer'),
                cognito_user_pools=[user_pool],
                identity_source=apigw_.IdentitySource.header('Authorization')
            )

        return api, authorizer


    # ── API ENDPOINTS ──────────────────────────────────────────────────────────

    def create_oauth2_endpoint(self, api: apigw_.RestApi, user_pool_domain: cognito_.UserPoolDomain) -> None:
        api.root.add_resource('oauth2').add_resource('token').add_method(
            'POST',
            apigw_.HttpIntegration(
                url=f'https://{user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com/oauth2/token',
                http_method='POST'
            )
        )

    def create_mod_medicaid_endpoints(self, api: apigw_.RestApi, authorizer, api_scope, api_handler: lambda_.Function) -> None:
        demo_ingestion = api.root.add_resource('demo_ingestion')
        demo_ingestion.add_method(
            'POST',
            apigw_.LambdaIntegration(api_handler, proxy=True),
            authorizer=authorizer,
            authorization_type=apigw_.AuthorizationType.COGNITO,
        )

        tms_settings = api.root.add_resource('tms_settings')
        tms_settings.add_method(
            'GET',
            apigw_.LambdaIntegration(api_handler, proxy=True),
            authorizer=authorizer,
            authorization_type=apigw_.AuthorizationType.COGNITO,
        )
        tms_settings.add_method(
            'POST',
            apigw_.LambdaIntegration(api_handler, proxy=True),
            authorizer=authorizer,
            authorization_type=apigw_.AuthorizationType.COGNITO,
        )

        dashboard_res = api.root.add_resource('dashboard')
        dashboard_res.add_method(
            'GET',
            apigw_.LambdaIntegration(api_handler, proxy=True),
            authorizer=authorizer,
            authorization_type=apigw_.AuthorizationType.COGNITO,
        )

        if api_scope:
            # Full TAPI endpoints — require Cognito authorizer and api_scope
            lyft_v1    = api.root.add_resource('v1')
            tapi       = lyft_v1.add_resource('tapi')
            tapi_trips = tapi.add_resource('trips')

            tapi_providers = tapi.add_resource('providers')
            tapi_providers.add_method(
                'GET',
                apigw_.LambdaIntegration(api_handler, proxy=True),
                authorizer=authorizer,
                authorization_scopes=[api_scope.auth_scope]
            )

            tapi_trips.add_method(
                'POST',
                apigw_.LambdaIntegration(api_handler, proxy=True),
                authorizer=authorizer,
                authorization_scopes=[api_scope.auth_scope]
            )

            tapi_update = tapi_trips.add_resource('{trip_id}')
            tapi_update.add_method(
                'PUT',
                apigw_.LambdaIntegration(api_handler, proxy=True),
                authorizer=authorizer,
                authorization_scopes=[api_scope.auth_scope]
            )

            tapi_cancel = tapi_update.add_resource('cancel')
            tapi_cancel.add_method(
                'POST',
                apigw_.LambdaIntegration(api_handler, proxy=True),
                authorizer=authorizer,
                authorization_scopes=[api_scope.auth_scope]
            )

    def create_kiosk_deprecated_endpoints(self, api: apigw_.RestApi, authorizer, kiosk_workerbee: lambda_.Function, kiosk_statusbee: lambda_.Function) -> None:
        connector_resource = api.root.add_resource('connector')
        connector_resource.add_method(
            'POST',
            apigw_.LambdaIntegration(kiosk_workerbee, proxy=True),
            authorizer=authorizer,
        )
        connector_resource_status = api.root.add_resource('connector_status')
        connector_resource_status.add_method(
            'POST',
            apigw_.LambdaIntegration(kiosk_statusbee, proxy=True),
            authorizer=authorizer,
        )

    def create_kiosk_endpoints(self, api: apigw_.RestApi, authorizer, api_handler: lambda_.Function) -> None:
        kiosk_resource = api.root.add_resource('kiosk_request')
        kiosk_resource.add_method(
            'POST',
            apigw_.LambdaIntegration(api_handler, proxy=True),
            authorizer=authorizer,
        )

        kiosk_resource = api.root.add_resource('kiosk_request_detail')
        kiosk_resource.add_method(
            'POST',
            apigw_.LambdaIntegration(api_handler, proxy=True),
            authorizer=authorizer,
        )

        kiosk_resource_status = api.root.add_resource('kiosk_status')
        kiosk_resource_status.add_method(
            'POST',
            apigw_.LambdaIntegration(api_handler, proxy=True),
            authorizer=authorizer,
        )

    def create_via_webhook_endpoint(self, api: apigw_.RestApi, api_handler: lambda_.Function) -> None:
        via_webhook = api.root.add_resource('via_webhook')
        via_webhook.add_method(
            'POST',
            apigw_.LambdaIntegration(api_handler, proxy=True)
        )

    def create_dashboard_endpoint(self, api: apigw_.RestApi, authorizer, dashboard_handler: lambda_.Function) -> None:
        dashboard_resource = api.root.add_resource('dashboard')
        dashboard_resource.add_method(
            'GET',
            apigw_.LambdaIntegration(dashboard_handler, proxy=True),
            authorizer=authorizer
        )


