import json, uuid

import boto3

from mod_medicaid.ViaConnection import ViaConnection
from mod_medicaid.AWS_Data_Operations import dd_new_trip, dd_scan_all_trips
from mod_medicaid.mod_medicaid import lyft_trip_request
from mod_medicaid.lyft_via_xform import lyft_to_via
from mod_medicaid.webhooks import via_interpreter


def api_handler(event, context):
    # Obtain header information
    ep = event['requestContext']['resourcePath']
    try:
        payload = json.loads(event['body'])
    except:
        print('No Payload')
        payload = ''
    status_code = 200
    print(payload)
    print(ep)
    output = event

    # Legacy Lyft TAPI code
    if ep == '/v1/tapi/trips/{trip_id}/cancel':
        output = 'Not Available'
        status_code = 404
    elif ep == '/v1/tapi/trips/{trip_id}':
        output = 'Not Available'
        status_code = 404
    elif ep == '/v1/tapi/trips':
        output = 'Not Available'
        status_code = 404
    elif ep == '/kiosk_status' or ep == '/connector_status':
        try:
            vc = ViaConnection()
            output = vc.via_kiosk_trip_status(payload)
        except ValueError as e:
            output = str(e)
            status_code = 200
        except SystemError as e:
            output = str(e)
            status_code = 400
    # NOTE: Kiosk request was broken into two separate calls to keep the
    #           API calls under 30 seconds per API Gateway limits
    elif ep == '/kiosk_request' or ep == '/connector':
        try:
            vc = ViaConnection()
            output = vc.via_request_book_trip(payload)
            dd_new_trip(via_response=output)             
        except ValueError as e:
            output = str(e)
            status_code = 200
        except SystemError as e:
            output = str(e), 500
            # TODO: need to let front end accept this error code
            # status_code = 500
    elif ep == '/kiosk_request_detail':
        try:
            vc = ViaConnection()
            output = vc.via_trip_details(payload['trip_id'])
        except SystemError as e:
            print(e)
            output = str(e)

    elif ep == '/demo_ingestion':
        try:
            import secrets_loader as _sl
            creds = _sl.get_credentials()
            _TMS_LABELS = {
                'via_api_url':       'API Base URL',
                'via_client_id':     'Client ID',
                'via_client_secret': 'Client Secret',
                'via_api_key':       'API Key',
                'via_auth_url':      'Token URL',
                'tms_service_tag':   'Service Tag',
            }
            missing = [label for key, label in _TMS_LABELS.items() if not creds.get(key)]
            if missing:
                output      = {'error': f'TMS settings are incomplete. Please configure the following fields in TMS Settings: {", ".join(missing)}'}
                status_code = 422
            else:
                # Capture the Via-format payload separately so the frontend can display all 3 stages
                via_payload    = lyft_to_via(payload)
                print(f'Via Payload: {via_payload}')
                result         = lyft_trip_request(payload)
                print(f'Lyft Response: {result}')
                lyft_response, resp_status = result if isinstance(result, tuple) else (result, 200)
                output = {
                    'broker_request': payload,
                    'via_payload':    via_payload,
                    'response':       lyft_response,
                }
                status_code = resp_status
        except Exception as e:
            output      = {'error': str(e)}
            status_code = 500

    elif ep == '/tms_settings':
        try:
            import os as _os, secrets_loader as _sl
            secret_name = _os.environ['SECRETS_NAME']
            region      = _os.environ.get('AWS_REGION', 'ap-south-1')
            sm          = boto3.session.Session().client('secretsmanager', region_name=region)
            if event.get('httpMethod') == 'GET':
                resp     = sm.get_secret_value(SecretId=secret_name)
                all_keys = json.loads(resp['SecretString'])
                output   = {k: v for k, v in all_keys.items() if k.startswith('tms_')}
            else:
                resp    = sm.get_secret_value(SecretId=secret_name)
                current = json.loads(resp['SecretString'])
                current.update({k: v for k, v in payload.items() if k.startswith('tms_')})
                sm.put_secret_value(SecretId=secret_name, SecretString=json.dumps(current))
                _sl._cached = None
                output = {'saved': True}
        except Exception as e:
            output      = {'error': str(e)}
            status_code = 500

    elif ep == '/dashboard' and event.get('httpMethod') == 'GET':
        try:
            from datetime import datetime, timedelta, timezone
            from zoneinfo import ZoneInfo
            import json as _json

            CHICAGO = ZoneInfo('America/Chicago')
            STATUS_MAP = {
                'CONFIRMED': 'booked',  'REQUESTED': 'booked',
                'CANCELLED': 'canceled', 'CANCELED': 'canceled',
                'COMPLETED': 'completed', 'DISPATCHED': 'dispatched',
            }

            def _addr(d):
                return ', '.join(filter(None, [
                    d.get('address_line1', ''), d.get('city', ''),
                    d.get('state', ''), d.get('zip', '')]))

            def _fmt_dt(s):
                try:
                    dt = datetime.fromisoformat(s).replace(tzinfo=timezone.utc).astimezone(CHICAGO)
                    return dt.strftime('%Y-%m-%d %I:%M %p')
                except Exception:
                    return s

            now_ch       = datetime.now(CHICAGO)
            today        = now_ch.date()
            yesterday    = today - timedelta(days=1)
            this_month   = (today.year, today.month)
            prev_month_d = today.replace(day=1) - timedelta(days=1)
            last_month   = (prev_month_d.year, prev_month_d.month)

            items = dd_scan_all_trips()

            trips_today = trips_yesterday = booked_total = 0
            booked_this_month = booked_last_month = canceled_total = 0
            mapped = []

            for item in items:
                lyft  = _json.loads(item.get('lyft_request_payload') or '{}')
                via   = _json.loads(item.get('via_response_payload') or '{}')
                rider  = lyft.get('rider', {})
                origin = lyft.get('origin', {}).get('address', {})
                dest   = lyft.get('destination', {}).get('address', {})

                raw_status = via.get('trip_status', '').upper()
                status     = STATUS_MAP.get(raw_status, raw_status.lower())
                is_canceled = status == 'canceled'

                try:
                    item_dt   = datetime.fromisoformat(item.get('request_time', '')).replace(tzinfo=timezone.utc).astimezone(CHICAGO)
                    item_date = item_dt.date()
                except Exception:
                    item_date = None

                if item_date == today:     trips_today     += 1
                if item_date == yesterday: trips_yesterday += 1
                if is_canceled:
                    canceled_total += 1
                else:
                    booked_total += 1
                    if item_date and (item_date.year, item_date.month) == this_month:
                        booked_this_month += 1
                    if item_date and (item_date.year, item_date.month) == last_month:
                        booked_last_month += 1

                mapped.append({
                    'broker_trip_id': item.get('tapi_trip_id', ''),
                    'internal_id':    item.get('atms_ride_id', ''),
                    'via_trip_id':    item.get('via_trip_id', ''),
                    'rider':          f"{rider.get('first_name', '')} {rider.get('last_name', '')}".strip(),
                    'pickup':         _addr(origin),
                    'destination':    _addr(dest),
                    'status':         status,
                    'booked_at':      _fmt_dt(item.get('request_time', '')),
                    '_sort_key':      item.get('request_time', ''),
                    'payload':        {'lyft': lyft, 'via': via},
                })

            mapped.sort(key=lambda r: r['_sort_key'], reverse=True)
            for r in mapped:
                del r['_sort_key']

            output = {
                'trips': mapped,
                'stats': {
                    'trips_today':       trips_today,
                    'trips_yesterday':   trips_yesterday,
                    'booked_total':      booked_total,
                    'booked_this_month': booked_this_month,
                    'booked_last_month': booked_last_month,
                    'canceled_total':    canceled_total,
                    'total_trips':       len(items),
                },
            }
        except Exception as e:
            output      = {'error': str(e)}
            status_code = 500

    elif ep == '/via_webhook':
        try:
            output = via_interpreter(event)
        except Exception as e:
            print(e)
            output = ''
    elif ep == '/v1/tapi/providers':
        output = 'Not Available'
        status_code = 404
    return {
        'isBase64Encoded': False,
        'statusCode': status_code,
        'body': json.dumps(output),
        'headers': {
            'content-type': 'application/json',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        }
    }

# Legacy code
def lambda_kiosk(event, context):
    return api_handler(event, context)

def lambda_kiosk_status(event, context):
    return api_handler(event, context)