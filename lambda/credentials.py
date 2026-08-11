# On-prem development template — fill in locally, do NOT commit actual values.
# On AWS, credentials are fetched from Secrets Manager via secrets_loader.py.

# Via Credentials
via_client_id = ''
via_client_secret = ''
via_api_key = ''
via_auth_url = 'https://trip-api.auth.us-east-1.amazoncognito.com/oauth2/token'
via_api_url = 'us-east-1.trip-api.ridewithvia.com'

# Lyft Credentials
lyft_client_id = ''
lyft_client_secret = ''
lyft_program_id = ''
lyft_auth_url = 'https://api.lyft.com/oauth/token'
lyft_api_url = 'https://api.lyft.com/v1/tapi/atms/webhooks'