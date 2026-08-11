# On-prem / local development only.
# Copy this file to lambda/credentials.py and fill in values from your Via and Lyft dashboards.
# lambda/credentials.py is gitignored — never commit it with real credentials.
#
# On AWS, credentials are fetched at runtime from Secrets Manager via secrets_loader.py.
# This file is only used when os.environ['Execution'] == 'On_Prem'.

# Via Credentials
via_client_id = 'YOUR_VIA_CLIENT_ID'
via_client_secret = 'YOUR_VIA_CLIENT_SECRET'
via_api_key = 'YOUR_VIA_API_KEY'
via_auth_url = 'https://trip-api.auth.us-east-1.amazoncognito.com/oauth2/token'
via_api_url = 'us-east-1.trip-api.ridewithvia.com'

# Lyft Credentials
lyft_client_id = 'YOUR_LYFT_CLIENT_ID'
lyft_client_secret = 'YOUR_LYFT_CLIENT_SECRET'
lyft_program_id = 'YOUR_LYFT_PROGRAM_ID'
lyft_auth_url = 'https://api.lyft.com/oauth/token'
lyft_api_url = 'https://api.lyft.com/v1/tapi/atms/webhooks'
