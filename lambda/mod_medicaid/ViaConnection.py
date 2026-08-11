from pprint import pprint
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import boto3
from botocore.exceptions import ClientError
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
from requests.auth import HTTPBasicAuth

class ViaConnection:
    def __init__(self, on_prem=False):
        # set timezone and now
        self._time_zone = ZoneInfo('America/Chicago')
        self._now = datetime.now(tz=self._time_zone)
        self._now_timestamp = self._now.timestamp()
        self._region='us-west-1'
        
        # get credentials
        self._secret = self._get_aws_secret()
        
        # set internal vars
        self._rider = None
        self._rider_id = None
        self._rider_hc = False

        # instatiate the oauth flow by default
        # This shares the connection and reduces chatter
        self._oauth = self._initiate_oauth()

    def __del__(self):
        # oauth cleanup - close connection
        self._oauth.close()
        print("closing oauth")

    # get API connection info from AWS Secrets Manager (or on-prem fallback via secrets_loader)
    def _get_aws_secret(self):
        from secrets_loader import get_credentials
        return get_credentials()
    
    def _initiate_oauth(self):
        # get credentials
        auth_url = self._secret['via_auth_url']
        client_id = self._secret['via_client_id']
        client_secret = self._secret['via_client_secret']
        api_key = self._secret['via_api_key']
        # initiate oauth
        auth = HTTPBasicAuth(client_id, client_secret)
        client = BackendApplicationClient(client_id=client_id)
        with OAuth2Session(client=client) as oauth:   
            oauth.fetch_token(token_url=auth_url, auth=auth, data={
                'grant_type':'client_credentials',
            })
            oauth.headers.update({
                'x-api-key': api_key
            }) 
        return oauth
    
    # gets rider details from parameter - ONLY ONE
    # TODO: need to fix if get_rider_details returns more than one pax.
    # Valid params
    #   email
    #   via's rider_id
    #   date of birth in ISO 8601: yyyy-mm-dd
    #   phone number in E.164: +12345678989
    def get_rider_details(self, **kwargs):
        if self._secret is None:
            return None

        # Cleaning payload of None and '''
        payload = {k:v for k,v in kwargs.items() if v}

        # Correct 'email_address' to 'email'
        if 'email_address' in payload:
            payload['email'] = payload['email_address']
            payload.pop('email_address')

        # Prioritize Phone Number, then Email
        priority = ['phone_number', 'email']
        for p in priority:
            if p in payload:
                rider_data = self._ping_via_for_rider({p: payload[p]})
                if len(rider_data) > 0:
                    break

        if len(rider_data) > 0:             
            return rider_data
        else:
            raise ValueError("MOD/ATMS Error: You are not currently enrolled in HIRTA or Health Connector. Please check your personal information, call (877) 686-0029 or see the front desk to register.")

    def _ping_via_for_rider(self, payload):
        r = self._oauth.get(f'https://{self._secret['via_api_url']}/riders', params=payload)
        if r.status_code in (500, 400):
            raise SystemError(f'Error: {json.dumps(r.json())}')
        data = r.json()
        # return rider data if exists
        if 'riders' in data:
            return data['riders'][0]
        else:
            return []

    # Set rider information
    # In addition to params accepted for get_rider_details, also can pass via payload.
    def set_rider_info(self, payload=None, **kwargs):
        # Handle payloads for via
        if payload:
            kwargs = {k:v for k,v in payload['passenger_info'].items() if k in ['phone_number', 'email']}

        rider = self.get_rider_details(**kwargs)
        self._rider = rider
        self._rider_id = rider['rider_id']
        self._rider_hc = rider.get('sub_services', {}).get('Health_Connector', False)

    def set_trip_params(self):
        week_ahead = int((self._now + timedelta(weeks=1)).timestamp())
        pickup_time_range = {'start_timestamp': int(self._now_timestamp), 'end_timestamp': week_ahead}
        params = {
            'rider_id':self._rider_id, 'page_number':0, 'page_list_size':100, 
            'pickup_time_range': json.dumps(pickup_time_range)
            }
        return params

    # returns all trips for a rider_id
    def via_get_trips(self):
        # set parameters
        params = self.set_trip_params()
        # loop through pages of trips in /trips/get
        all_trips = []
        pages_remaining = True
        while pages_remaining:
            # update page number
            params['page_number'] += 1
            # make call to trips/get for rider_id and page number
            r = self._oauth.get(f'https://{self._secret['via_api_url']}/trips/get', params=params)
            if r.status_code in (500, 400):
                raise SystemError(f'Error: {json.dumps(r.json())}')
            # add trip data to the all_trips list
            data = r.json()
            all_trips.extend(data['trips'])
            # check if there are pages remaining
            pages_remaining = data['has_next']
        return all_trips

    # returns next trip for a rider_id
    # TODO: Check if this meets the outputs needed from old design.
    def via_get_next_trip(self, **kwargs):
        # set rider if it doesn't exist
        if not self._rider:
            self.set_rider_info(**kwargs)
        # get all trips for rider_id
        all_trips = self.via_get_trips()   
        # filter out trips with invalid statuses and pickups in the past
        okay_stat = ['PENDING', 'PICKUP_DETERMINED', 'CONFIRMED','ASSIGNED', 'ARRIVED', 'BOARDED']
        valid_trips = [t for t in all_trips if t['trip_status'] in okay_stat]
        upcoming_trips = [t for t in valid_trips if ('pickup_eta' in t) and (t['pickup_eta'] > self._now_timestamp)]      
        # check if rider_id has no trips
        if len(upcoming_trips) == 0:
            raise ValueError("MOD/ATMS Error: No upcoming trips")
        # get trip with the smallest (nearest) pickup eta
        else:
            # sort trips by descending pickup time
            sorted_trips = sorted(upcoming_trips, key=lambda d: d['pickup_eta'], reverse=True)
            # get the trip with the smallest pickup time
            trip = sorted_trips.pop()
            return trip

    # request and book a trip
    def via_request_book_trip(self, payload):
        request_data = self.via_request_trip(payload)
        ## Deal with error on no bookings available.
        print(request_data)
        if len(request_data['trips']) > 0:
            trip_id = request_data['trips'][0].get('trip_id')
            return self.via_book_trip(trip_id)
        else:
            raise SystemError(f'MOD/ATMS Error: {json.dumps(request_data.json())}')

    # request a trip
    def via_request_trip(self, payload):
        # set rider if it doesn't exist
        if not self._rider:
            self.set_rider_info(payload=payload)

        # if they are qualified, use the Health Connector sub_service.
        payload['sub_service'] = 'Health_Connector' if self._rider_hc else 'NEMT'
        print(payload)
        # Request Trip Flow
        r_request = self._oauth.post(f'https://{self._secret['via_api_url']}/trips/request', json=payload)
        if r_request.status_code in (500, 400):
            raise SystemError(f'Error: {json.dumps(r_request.json())}')
        request_data = r_request.json()
        return request_data

        # Write book flow here
        # book Trip Flow
    def via_book_trip(self, trip_id):
        r_booked = self._oauth.post(f'https://{self._secret['via_api_url']}/trips/book', json={'trip_id': trip_id})        

        return r_booked.json()      

    # Get trip details
    def via_trip_details(self, trip_id):
        details = self._oauth.get(f'https://{self._secret['via_api_url']}/trips/details', params={'trip_id': trip_id})
        return details.json()        

    def via_kiosk_trip_status(self, rider):
        the_next_trip = self.via_get_next_trip(**rider)
        trip_deets = self.via_trip_details(the_next_trip['trip_id'])
        return trip_deets
