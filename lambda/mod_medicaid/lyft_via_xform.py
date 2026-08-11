# Converts Lyft's JSON trip request response to Via request
import uuid
from datetime import datetime


# Converts Lyft ride request to dictionary containing expected Via formatting and required information
def lyft_to_via(lyft_request_response):

    # If field is empty, return blank dictionary, string, or "0" in case of passenger count

    additional_passengers = int(len(lyft_request_response.get('demand_additional_info',{}).get('additional_riders',[])))

    arrive_at = "" # datetime.fromisoformat(lyft_request_response.get('appointment_time',"")).timestamp() #optional

    depart_at = datetime.fromisoformat(lyft_request_response.get('pickup_time',"")).timestamp()

    destination = {
        'lat':lyft_request_response.get('destination',{}).get('lat',""), #required
        'lng':lyft_request_response.get('destination',{}).get('lng',""), #required
        'address':(lyft_request_response.get('destination',{}).get('address',{}).get('address_line1',"")+", "
                +lyft_request_response.get('destination',{}).get('address',{}).get('city',"")+", "
                +lyft_request_response.get('destination',{}).get('address',{}).get('state',"")+" "
                +lyft_request_response.get('destination',{}).get('address',{}).get('zip',"")), #optional
    }

    origin = {
        'lat':lyft_request_response.get('origin',{}).get('lat',""), #required
        'lng':lyft_request_response.get('origin',{}).get('lng',""), #required
        'address':(lyft_request_response.get('origin',{}).get('address',{}).get('address_line1',"")+", "
                +lyft_request_response.get('origin',{}).get('address',{}).get('city',"")+", "
                +lyft_request_response.get('origin',{}).get('address',{}).get('state',"")+" "
                +lyft_request_response.get('origin',{}).get('address',{}).get('zip',"")), #optional
    }

    # Rider + additional passenger count
    passenger_count = 1 + additional_passengers #required

    #
    rider_identifier = {
        'first_name':lyft_request_response.get('rider',{}).get('first_name',""),
        'last_name':lyft_request_response.get('rider',{}).get('last_name',""),
        'phone_number':lyft_request_response.get('rider',{}).get('phone',""),
        'email':lyft_request_response.get('rider',{}).get('first_name',"")+'.'+lyft_request_response.get('rider',{}).get('last_name',"")+'@hirta.com'
    }


    import secrets_loader as _sl
    subservice = _sl.get_credentials().get('tms_service_tag', '')

    # Need to store TAPI trip ID for reference back to Lyft
    tapi_trip_id = lyft_request_response.get('tapi_trip_id',"")

    ride_info = {
         'additional_passengers':{"Guest":passenger_count-1},
        # 'arrive_at':arrive_at,
        'depart_at':depart_at,
        'destination':destination,
        'origin': origin,
        'passenger_count': passenger_count,
        'sub_service': subservice, 
        'passenger_info': rider_identifier
    }

    return(ride_info)

# Converts Via booking response to dictionary containing expected Lyft formatting and required information
def via_to_lyft(via_return_data, lyft_response, atms_ride_id):

    # ATMS Rider ID
    atms_ride_id = atms_ride_id

    # Appointment Time
    appointment_time = lyft_response.get('appointment_time',"")

    # Destination fields
    destination = {
        'lat':via_return_data.get('dropoff',{}).get('lat',0),
        'lng':via_return_data.get('dropoff',{}).get('lng',0),
        'address':via_return_data.get('dropoff',{}).get('description',"")
    }

    # Origin fields
    origin = {
        'lat':via_return_data.get('pickup',{}).get('lat',0),
        'lng':via_return_data.get('pickup',{}).get('lng',0),
        'address':via_return_data.get('pickup',{}).get('description',"")
    }
    
    # Rider
    rider = {
        'first_name':lyft_response.get('rider',{}).get('first_name',""),
        'last_name':lyft_response.get('rider',{}).get('last_name',""),
        'phone':lyft_response.get('rider',{}).get('phone',""),
        'atms_rider_id': str(uuid.uuid4())#lyft_response.get('rider',{}).get('atms_rider_id',"")
    }

    # Demand Additional Info
    demand_additional_info = {
        'vehicle_type':lyft_response.get('demand_additional_info',{}).get('vehicle_type',"")
    }

    # Compile JSON
    lyft_response = {
        'broker_trip_id': lyft_response.get('trip_source_name',{}).get('broker_trip_id',""),
        'rides':[
            {
                'appointment_time':appointment_time,
                'atms_ride_id':atms_ride_id,
                # 'tapi_trip_id': lyft_trip_data['tapi_trip_id'],
                'destination':destination,
                'origin':origin,
                'rider':rider,
                'demand_additional_info':demand_additional_info
            }
        ]
    }

    return lyft_response