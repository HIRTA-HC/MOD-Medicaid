import json
import os
import boto3
from botocore.exceptions import ClientError

_cached = None


def get_credentials() -> dict:
    """Return credentials dict, fetched once per warm Lambda instance."""
    global _cached
    if _cached is not None:
        return _cached

    if os.environ.get('Execution') == 'On_Prem':
        import credentials as _creds
        _cached = {
            'via_client_id':      _creds.via_client_id,
            'via_client_secret':  _creds.via_client_secret,
            'via_api_key':        _creds.via_api_key,
            'via_auth_url':       _creds.via_auth_url,
            'via_api_url':        _creds.via_api_url,
            'lyft_client_id':     _creds.lyft_client_id,
            'lyft_client_secret': _creds.lyft_client_secret,
            'lyft_program_id':    _creds.lyft_program_id,
            'lyft_auth_url':      _creds.lyft_auth_url,
            'lyft_api_url':       _creds.lyft_api_url,
        }
    else:
        secret_name = os.environ['SECRETS_NAME']
        region = os.environ.get('AWS_REGION', 'us-west-1')
        client = boto3.session.Session().client('secretsmanager', region_name=region)
        try:
            resp = client.get_secret_value(SecretId=secret_name)
        except ClientError as e:
            raise RuntimeError(f'Failed to fetch secret "{secret_name}": {e}') from e
        raw = json.loads(resp['SecretString'])
        # tms_* keys are the single source for Via credentials; map to the names
        # used by ViaConnection.py / via_request.py / webhooks.py unchanged.
        _cached = {
            'via_client_id':      raw.get('tms_client_id', ''),
            'via_client_secret':  raw.get('tms_client_secret', ''),
            'via_api_key':        raw.get('tms_api_key', ''),
            'via_auth_url':       raw.get('tms_token_url', ''),
            'via_api_url':        raw.get('tms_api_base_url', ''),
            'tms_service_tag':    raw.get('tms_service_tag', ''),
            'via_hmac_key':       raw.get('via_hmac_key', ''),
            'lyft_client_id':     raw.get('lyft_client_id', ''),
            'lyft_client_secret': raw.get('lyft_client_secret', ''),
            'lyft_program_id':    raw.get('lyft_program_id', ''),
            'lyft_auth_url':      raw.get('lyft_auth_url', ''),
            'lyft_api_url':       raw.get('lyft_api_url', ''),
        }

    return _cached
