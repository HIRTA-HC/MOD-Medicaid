import requests, os
import json
import secrets, string, hmac, base64
from hashlib import sha256
from pprint import pprint
from datetime import datetime, timezone
from uuid import uuid4

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
from requests.auth import HTTPBasicAuth

from .AWS_Data_Operations import dd_retrieve_by_via_trip_id
from secrets_loader import get_credentials


# RIGHT NOW THIS RETURNS EVERYTHING BACK VIA THE WEBHOOK FOR TESTING

environ = os.environ.get('Execution')


def via_interpreter(event):
	incoming_payload = json.loads(event['body'])
	# this is used to call functions below
	ride_status_codes_translator= dict(
		Pending=None,
		Confirmed=scheduled,
		# HIRTA does not offer Will Call willcall_notified
		Pickup_Determined=None, # this could be scheduled,
		Assigned=dispatched,
		Arrived=arrived,
		Boarded=picked_up,
		# nothing available for arrived_dropoff
		Finished=dropped_off,
		Canceled=canceled,
		No_Show=canceled, #canceled_no_show reason
		Not_Available=canceled #canceled_atms_failure reason
	)

	via_hmac_key = get_credentials().get('via_hmac_key', '')
	if not via_hmac_key:
		return {'error': 'HMAC key not configured'}

	# Create Crypto secure random string to force fail via sig if no sig is detected.
	crypto_random_str = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(20))
	raw_payload = event['body']
	via_sig = event['headers'].get('X-Via-Signature', crypto_random_str)
	dig = hmac.digest(raw_payload.encode(), via_hmac_key.encode(), sha256)
	deco_dig = base64.b64encode(dig).decode()

	print(deco_dig)
	print('via_sig', via_sig)

	hmac_auth = hmac.compare_digest(
		deco_dig, via_sig
	)

	# Call the above if not None
	status = list({ele for ele in ride_status_codes_translator if ride_status_codes_translator[ele]}) 

	if incoming_payload['trip_status'] in status and hmac_auth:
		print(incoming_payload['trip_status'])
		return ride_status_codes_translator[incoming_payload['trip_status']](incoming_payload)
	else:
		return ("No data available!!!")

def lyft_send_message(payload):
	print(payload)

	creds = get_credentials()
	lyft_client_id = creds['lyft_client_id']
	lyft_client_secret = creds['lyft_client_secret']
	lyft_program_id = creds['lyft_program_id']
	lyft_auth_url = creds['lyft_auth_url']
	lyft_api_url = creds['lyft_api_url']

	# Need to update against Lyft's needs here, slighty different than Via's
	auth = HTTPBasicAuth(lyft_client_id, lyft_client_secret)
	client = BackendApplicationClient(client_id=lyft_client_id)
	params = {
	    'grant_type':'client_credentials',
	}

	with OAuth2Session(client=client) as lyft_oauth: 

		# Need to update against Lyft's needs here, slighty different than Via's
	    token = lyft_oauth.fetch_token(token_url=lyft_auth_url, auth=auth, data=params)
	    # Bearer token needed??
	    lyft_oauth.headers.update({
	        'x-lyft-program-id': lyft_program_id
	    })

	    r = lyft_oauth.post(f'https://{lyft_api_url}', json=payload)

	return payload

def create_message(event):
	return dict(
		event_id=str(uuid4()),
		occurred_at=datetime.now(timezone.utc).isoformat(),
		event_type="tapi_trip.status.updated",
		event=event
	)

def query_ids(via_trip_id):
	# some code to query
	if environ == 'On_Prem':
		broker_trip_id=str(uuid4())
		tapi_trip_id=str(uuid4())
		atms_ride_id=str(uuid4())
	elif environ == 'On_AWS':
		# Get original data
		full_data = dd_retrieve_by_via_trip_id(via_trip_id)
		orig_lyft_req = json.loads(full_data['lyft_request_payload'])

		broker_trip_id = orig_lyft_req.get('trip_source_name', {}).get('broker_trip_id', '')
		tapi_trip_id = full_data.get('tapi_trip_id', '')
		atms_ride_id = full_data.get('atms_ride_id', '')

	return dict(
		broker_trip_id=broker_trip_id,
		tapi_trip_id=tapi_trip_id,
		atms_trip_id=atms_ride_id # Pretty sure this is our PK
	)

# Generates record timestamps to be included with webhooks
def recorded_at(dtm):
	return {
		'recorded_at': dtm.isoformat(),
		'recorded_at_ms':  dtm.timestamp(),

	}

# Generates location information dictionary to be included with webhooks
def location(x):
	info = x['vehicle_info']['current_location']
	return {
		'location': {
			'lat': info['lat'],
			'lng': info['lng'],
		}
	}

# Generates driver information dictionary to be included with webhooks
def driver(x):
	info = x['driver_info']

	return {
		'driver': dict(
			first_name=info['first_name'],
			last_name=info['last_name'],
			phone=info['phone_number'],
			license='',
			atms_driver_id=''
		)
	}

# Generates vehicle information dictionary to be included with webhooks
def vehicle(x):
	info = x['vehicle_info']
	return {
		'vehicle': dict(
			make='',
			model=info['model'],
			color=info['color'],
			vin='',
			license_plate=info['license_plate'],
			license_state='IA',
			atms_vehicle_id=''
		)
	}

# Generates scheduled webhook
def scheduled(via):
	event_dtm = datetime.fromtimestamp(via['last_status_change_timestamp'], timezone.utc)

	return lyft_send_message(create_message({
		**query_ids(via['trip_id']),
		**recorded_at(event_dtm),
		'status': "scheduled"
	}))

# Generates willcall notified webhook
def willcall_notified(via):
	event_dtm = datetime.now(timezone.utc)

	return lyft_send_message(create_message({
		**query_ids(via['trip_id']),
		**recorded_at(event_dtm),
		'status': "willcall_notified"
	}))

# Generates dispatched webhook
def dispatched(via):
	event_dtm = datetime.fromtimestamp(via['last_status_change_timestamp'], timezone.utc)
	pickup_dtm = datetime.fromtimestamp(via['latest_pickup_eta'], timezone.utc)

	return lyft_send_message(create_message({
		**query_ids(via['trip_id']),
		**recorded_at(event_dtm),
		'status': "dispatched",
		'eta_pickup': pickup_dtm.isoformat(), #being sent as iso?
		**location(via),
		**driver(via),
		**vehicle(via)
	}))

# Generates arrived webhook
def arrived(via):
	event_dtm = datetime.fromtimestamp(via['driver_arrival_timestamp'], timezone.utc)

	return lyft_send_message(create_message({
		**query_ids(via['trip_id']),
		**recorded_at(event_dtm),
		'status': "arrived",
		**location(via),
		**driver(via),
		**vehicle(via)
	}))

# Generates picked up webhook
def picked_up(via):
	event_dtm = datetime.fromtimestamp(via['rider_boarding_timestamp'], timezone.utc)
	dropoff_eta = datetime.fromtimestamp(via['latest_dropoff_eta'], timezone.utc)

	return lyft_send_message(create_message({
		**query_ids(via['trip_id']),
		**recorded_at(event_dtm),
		'status': "picked_up",
		'eta_dropoff': dropoff_eta.isoformat(), #being sent as iso?
		**location(via),
		**driver(via),
		**vehicle(via)
	}))

# Generates arrived dropped off webhook
def arrived_dropoff(via):
	event_dtm = datetime.now(timezone.utc)

	return lyft_send_message(create_message({
		**query_ids(via['trip_id']),
		**recorded_at(event_dtm),
		'status': "arrived_dropoff",
		**location(via),
		**driver(via),
		**vehicle(via)
	}))

# Generates dropped off webhook
def dropped_off(via):
	event_dtm = datetime.fromtimestamp(via['rider_dropoff_timestamp'], timezone.utc) 
	miles_driven = 0 # data not provided

	return lyft_send_message(create_message({
		**query_ids(via['trip_id']),
		**recorded_at(event_dtm),
		'status': "dropped_off",
		'actual_miles': miles_driven,
		**location(via),
		**driver(via),
		**vehicle(via)
	}))

# Generates canceled webhook
def canceled(via):
	event_dtm = datetime.fromtimestamp(via['last_status_change_timestamp'], timezone.utc)
	miles_driven = 0 # not provided

	#atms, dispatcher, driver - driver is not allowed to cancel
	canceled_by_map = dict(Canceled='dispatcher', No_Show='dispatcher', Not_Available='atms')
	canceled_by = 'dispatcher'

	cancel_map = dict(
		Canceled='dispatcher_rejected',
		No_Show='canceled_no_show',
		Not_Available='atms_failure'
		# No available map to canceled_at_door
	)
	reason_for_ride_cancellation = cancel_map[via['trip_status']]

	# This will never happen
	if canceled_by == 'driver':
		driver_cancelled = dict(
			location=dict(
				lat=lat,
				lng=lng,
			),
			driver=dict(
				first_name='',
				last_name='',
				phone='',
				license='',
				atms_driver_id=''
			),
			vehicle=dict(
				make='',
				model='',
				color='',
				vin='',
				license_plate='',
				license_state='IA',
				atms_vehicle_id=''
				)
		)
	else:
		driver_cancelled = {}

	return lyft_send_message(create_message({
		**query_ids(via['trip_id']),
		**recorded_at(event_dtm),
		'status': "canceled",
		'actual_miles': miles_driven,
		'canceled_by': canceled_by,
		'reason_for_ride_cancellation': reason_for_ride_cancellation, 
		**driver_cancelled

	}))

# Generates receipt ready webhook
def receipt_ready(via):
	event_dtm = datetime.now(timezone.utc)

	# This is triggerred by a terminating event: canceled or finshed

	return lyft_send_message(create_message({
		**query_ids(via['trip_id']),
		'data_source_ride_receipt_recorded_time': event_dtm.isoformat(),
		'stops': [], # Array of past stuff
		**driver(via),
		**vehicle(via)

	}))

# Generates GPS update webhook
def gps_update(via):
	event_dtm = datetime.now(timezone.utc) #actually don't have this GPS update time.

	return lyft_send_message(create_message({
		**query_ids(via['trip_id']),
		**recorded_at(event_dtm),
		**location(via),
		**vehicle(via)
	}))