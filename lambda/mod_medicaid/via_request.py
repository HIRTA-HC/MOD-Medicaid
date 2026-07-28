#imports requested ride_info, submits Via ride request, books ride

import requests
import time
import json
from pprint import pprint
from datetime import datetime
from zoneinfo import ZoneInfo

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
from requests.auth import HTTPBasicAuth

from secrets_loader import get_credentials

# Returns rider information based on rider ID
def via_rider_details(rider_id):
    creds = get_credentials()
    client_id = creds['via_client_id']
    client_secret = creds['via_client_secret']
    via_api_key = creds['via_api_key']
    via_auth_url = creds['via_auth_url']
    via_api_url = creds['via_api_url']

    auth = HTTPBasicAuth(client_id, client_secret)
    client = BackendApplicationClient(client_id=client_id)
    params = {
        'grant_type':'client_credentials',
    }

    with OAuth2Session(client=client) as via_oauth:

        token = via_oauth.fetch_token(token_url=via_auth_url, auth=auth, data=params)
        via_oauth.headers.update({
            'x-api-key': via_api_key
        })

        r = via_oauth.get(f'https://{via_api_url}/riders', params=dict(rider_id=rider_id))

        if r.status_code in (500, 400):
            raise SystemError(f"MOD/ATMS Error: {json.dumps(r.json())}")

    return r.json()

# Returns rider ID based on ride information
def via_get_rider_id(ride_info):
    creds = get_credentials()
    client_id = creds['via_client_id']
    client_secret = creds['via_client_secret']
    via_api_key = creds['via_api_key']
    via_auth_url = creds['via_auth_url']
    via_api_url = creds['via_api_url']

    auth = HTTPBasicAuth(client_id, client_secret)
    client = BackendApplicationClient(client_id=client_id)
    params = {
        'grant_type':'client_credentials',
    }

    with OAuth2Session(client=client) as via_oauth:
        token = via_oauth.fetch_token(token_url=via_auth_url, auth=auth, data=params)
        via_oauth.headers.update({
            'x-api-key': via_api_key
        })

        r = via_oauth.post(f'https://{via_api_url}/trips/request', json = ride_info)
        if r.status_code in (500, 400):
            raise SystemError(f"MOD/ATMS Error: {json.dumps(r.json())}")

    response = r.json()
    trip_id = response['trips'][0]['trip_id']

    r = via_oauth.get(f'https://{via_api_url}/trips/details', params=dict(trip_id=trip_id))
    if r.status_code in (500, 400):
        raise SystemError(f"trips/details response is: {json.dumps(r.json())}")

    response = r.json()
    rider_id = response['rider_id']

    return rider_id

#using create/rider
def via_get_rider_id_create(rider):
    creds = get_credentials()
    client_id = creds['via_client_id']
    client_secret = creds['via_client_secret']
    via_api_key = creds['via_api_key']
    via_auth_url = creds['via_auth_url']
    via_api_url = creds['via_api_url']

    auth = HTTPBasicAuth(client_id, client_secret)
    client = BackendApplicationClient(client_id=client_id)
    params = {
        'grant_type':'client_credentials',
    }

    with OAuth2Session(client=client) as via_oauth:
        token = via_oauth.fetch_token(token_url=via_auth_url, auth=auth, data=params)
        via_oauth.headers.update({
            'x-api-key': via_api_key
        })
        r = via_oauth.post(f'https://{via_api_url}/riders', json = rider)
        if r.status_code in (500, 400):
            raise SystemError(f"MOD/ATMS Error: {json.dumps(r.json())}")

    response = r.json()
    rider_id = response['rider_id']
    outcome = response['outcome']

    if outcome == 'existing':
        return rider_id
    else:
        raise SystemError("MOD/ATMS Error: Rider does not exist")

# Returns whether or not a rider exists in Via's system already
def via_rider_exists(ride_info):
    creds = get_credentials()
    client_id = creds['via_client_id']
    client_secret = creds['via_client_secret']
    via_api_key = creds['via_api_key']
    via_auth_url = creds['via_auth_url']
    via_api_url = creds['via_api_url']

    auth = HTTPBasicAuth(client_id, client_secret)
    client = BackendApplicationClient(client_id=client_id)
    params = {
        'grant_type':'client_credentials',
    }

    with OAuth2Session(client=client) as via_oauth:
        token = via_oauth.fetch_token(token_url=via_auth_url, auth=auth, data=params)
        via_oauth.headers.update({
            'x-api-key': via_api_key
        })

        r = via_oauth.post(f'https://{via_api_url}/trips/request', json = ride_info)

        ## Error Handling for Trip Request
        if r.status_code in (500, 400):
            raise SystemError(f"MOD/ATMS Error: {json.dumps(r.json())}")

    return "Rider exists"

# Requests trip after transformation from Lyft payload to Via
def via_request_trip(ride_info):
    creds = get_credentials()
    client_id = creds['via_client_id']
    client_secret = creds['via_client_secret']
    via_api_key = creds['via_api_key']
    via_auth_url = creds['via_auth_url']
    via_api_url = creds['via_api_url']

    auth = HTTPBasicAuth(client_id, client_secret)
    client = BackendApplicationClient(client_id=client_id)
    params = {
        'grant_type':'client_credentials',
    }

    with OAuth2Session(client=client) as via_oauth:
        token = via_oauth.fetch_token(token_url=via_auth_url, auth=auth, data=params)
        via_oauth.headers.update({
            'x-api-key': via_api_key
        })

        r = via_oauth.post(f'https://{via_api_url}/trips/request', json = ride_info)


        ## Error Handling for Trip Request
        if r.status_code in (500, 400):
            raise SystemError(f"MOD/ATMS Error: {json.dumps(r.json())}")

        ## this is Via's list of successful status messages requiring further action
        if r.status_code == 200:
            response = r.json()
            if "message" in response:
                message = response['message']
                if message in('NoAvailableSeats','NoPossiblePickupPoints', 'OriginNearDestination','OutOfServiceHours'):
                    raise SystemError(f"MOD/ATMS Error: {json.dumps(r.json())}")

        ## Book Requested Trip
        response = r.json()
        trips = response['trips']
        trip_id = {'trip_id': trips[0]['trip_id']}

        booked = via_oauth.post(f'https://{via_api_url}/trips/book', json = trip_id)

        if r.status_code in (500, 400):
            raise SystemError(f"MOD/ATMS Error: {json.dumps(booked.json())}")

        return booked.json()

# Cancels trip based on trip ID
def via_cancel_trip(trip_id):
    creds = get_credentials()
    client_id = creds['via_client_id']
    client_secret = creds['via_client_secret']
    via_api_key = creds['via_api_key']
    via_auth_url = creds['via_auth_url']
    via_api_url = creds['via_api_url']

    auth = HTTPBasicAuth(client_id, client_secret)
    client = BackendApplicationClient(client_id=client_id)
    params = {
        'grant_type':'client_credentials',
    }

    with OAuth2Session(client=client) as via_oauth:

        token = via_oauth.fetch_token(token_url=via_auth_url, auth=auth, data=params)
        via_oauth.headers.update({
            'x-api-key': via_api_key
        })

        r = via_oauth.post(f'https://{via_api_url}/trips/cancel', json=dict(trip_id=trip_id))

        if r.status_code in (500, 400):
            raise SystemError(f"MOD/ATMS Error: {json.dumps(r.json())}")

    return r.json()

# Returns trip details based on trip ID
def via_trip_details(trip_id):
    creds = get_credentials()
    client_id = creds['via_client_id']
    client_secret = creds['via_client_secret']
    via_api_key = creds['via_api_key']
    via_auth_url = creds['via_auth_url']
    via_api_url = creds['via_api_url']

    auth = HTTPBasicAuth(client_id, client_secret)
    client = BackendApplicationClient(client_id=client_id)
    params = {
        'grant_type':'client_credentials',
    }

    with OAuth2Session(client=client) as via_oauth:

        token = via_oauth.fetch_token(token_url=via_auth_url, auth=auth, data=params)
        via_oauth.headers.update({
            'x-api-key': via_api_key
        })

        r = via_oauth.get(f'https://{via_api_url}/trips/details', params=trip_id)

        if r.status_code in (500, 400):
            raise SystemError(f"MOD/ATMS Error: {json.dumps(r.json())}")

    return r.json()

def via_get_trips(trip_criteria):
    creds = get_credentials()
    client_id = creds['via_client_id']
    client_secret = creds['via_client_secret']
    via_api_key = creds['via_api_key']
    via_auth_url = creds['via_auth_url']
    via_api_url = creds['via_api_url']

    auth = HTTPBasicAuth(client_id, client_secret)
    client = BackendApplicationClient(client_id=client_id)
    params = {
        'grant_type':'client_credentials',
    }

    with OAuth2Session(client=client) as via_oauth:

        token = via_oauth.fetch_token(token_url=via_auth_url, auth=auth, data=params)
        via_oauth.headers.update({
            'x-api-key': via_api_key
        })

         # Get All Upcoming Trips through pagnination
        all_trips = []
        pages_remaining = True
        while pages_remaining:
            r = via_oauth.get(f'https://{via_api_url}/trips/get', params=trip_criteria)
            if r.status_code in (500, 400):
                raise SystemError(f"MOD/ATMS Error: {json.dumps(r.json())}")
            data = r.json()
            all_trips.extend(data['trips'])
            pages_remaining = data['has_next']
            trip_criteria['page_number'] += 1
            if trip_criteria['page_number'] > 10:
                break


        #non pandas version
        okay_stat = ['PENDING', 'PICKUP_DETERMINED', 'CONFIRMED','ASSIGNED', 'ARRIVED', 'BOARDED']
        filtered = [at for at in all_trips if at['trip_status'] in okay_stat]
        filtered2 = [f for f in filtered if f['dropoff_eta'] > datetime.now().timestamp()]
        smallest_time = min([int(f2['dropoff_eta']) for f2 in filtered2], default=0)
        df = [f2 for f2 in filtered2 if f2['dropoff_eta'] == smallest_time]
        if df == []:
            raise SystemError("MOD/ATMS Error: No upcoming trips")

    return df

# Gets trip status for a given rider
def via_check_status(rider):
    start_time = time.time()
    try:
        rider_id = via_get_rider_id_create(rider)
        trip = via_get_trips(trip_criteria = {'rider_id':rider_id,'page_number': 1,'page_list_size': 50})
        #I don't actually think this works but want to confirm there isn't an edge case I'm not thinking of
        if len(trip) < 1:
            return "MOD/ATMS Error: No upcoming trips"
        id = trip.pop()['trip_id']
        r = via_trip_details(trip_id={'trip_id': id})
        print("--- %s seconds ---" % (time.time() - start_time))
    except Exception as e:
        r = str(e)
    return r

# Debug Down here
if __name__ == "__main__":
    with open('test_ride_info.json') as f:
        ride_info = json.load(f)
    pprint(via_request_trip(ride_info))
