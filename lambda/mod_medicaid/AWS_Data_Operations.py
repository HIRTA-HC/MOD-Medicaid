import json, uuid, os
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Key


def _table(name_env: str):
    return boto3.resource('dynamodb').Table(os.environ[name_env])


def dd_new_trip(lyft_trip_data=None, atms_ride_id=str(uuid.uuid4()), via_response=None):
    table = _table('TABLE_NAME')

    #input data for table insertion
    # Protects dynamodb table if string is not provided, except for None
    tapi_trip_id = str(lyft_trip_data.get('tapi_trip_id')) if lyft_trip_data else None
    via_trip_id = via_response['trip_id']
    lyft_request_payload = json.dumps(lyft_trip_data) if lyft_trip_data else None
    via_response_payload = json.dumps(via_response) if via_response else None

    # Insert items into table.
    table.put_item(Item={
        "request_time": str(datetime.now()),
        "atms_ride_id": atms_ride_id,
        "tapi_trip_id": tapi_trip_id, 
        "via_trip_id":via_trip_id, 
        "lyft_request_payload": lyft_request_payload, 
        "via_response_payload": via_response_payload
    })
        
def dd_get_via_trip_id(tapi_trip_id):
    table = _table('TABLE_NAME')

    projection_expression = "via_trip_id"
    # projection_expression = "column1, column2"

    # Define the filter expression
    filter_expression = Key('tapi_trip_id').eq(tapi_trip_id)
    
    rows = table.scan(
        ProjectionExpression=projection_expression,
        FilterExpression=filter_expression
    )
    
    # Access the scanned items
    items = rows['Items'][0]
    via_trip_id = items['via_trip_id']

    return via_trip_id 


def dd_history_entry(old_entry):
    history_table = _table('HISTORY_TABLE_NAME')
    old_entry['update_time'] = str(int(round(datetime.now().timestamp(), 0)))

    history_table.put_item(Item=old_entry)


# Check rows:
def dd_retrieve_data(tapi_trip_id):
    table = _table('TABLE_NAME')
    filter_expression = Key('tapi_trip_id').eq(tapi_trip_id)
    rows = table.scan(
        FilterExpression=filter_expression
    )

    # Access the scanned items
    items = rows['Items'][0]

    return(items)
    

def dd_scan_all_trips() -> list:
    """Full paginated scan of MOD_Medicaid; handles DynamoDB 1 MB page limit."""
    table  = _table('TABLE_NAME')
    items  = []
    kwargs = {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get('Items', []))
        last = resp.get('LastEvaluatedKey')
        if not last:
            break
        kwargs['ExclusiveStartKey'] = last
    return items


def dd_retrieve_by_via_trip_id(via_trip_id):
    table = _table('TABLE_NAME')
    filter_expression = Key('via_trip_id').eq(via_trip_id)
    rows = table.scan(
        FilterExpression=filter_expression
    )

    # Access the scanned items
    items = rows['Items'][0]

    return(items)

if __name__ == "__main__":
    os.environ["TABLE_NAME"] = "MOD_Medicaid"
    test_event = {  "tapi_trip_id": "1234tapi_new", "lyft_request_payload": "lyft_request_payload_type1",\
                   "via_trip_id": "1234via_new",  "via_response_payload": "via_response_payload_type1"}
    result = api_handler(test_event, None)
    print(result)


# def dd_get_rider_id(fname, lname, ph, email):
#     dynamodb = boto3.resource('dynamodb')
#     table = 
#     try:



#     return 