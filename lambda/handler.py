import boto3
import json
import base64

print('Loading function')

object_list = ['Person', 'People', 'Human']

def lambda_handler(event, context):
    client = boto3.client('rekognition')
    response = client.detect_labels(
        Image={
            'Bytes': base64.b64decode(event['image']),
        },
        MaxLabels=5
    )
    print(response)

    client = boto3.client('iot-data', region_name='us-east-1')

    for item in response['Labels']:
        if item['Name'] in object_list:
            # Change topic, qos and payload
            response = client.publish(
                topic='sdk/objectDetected',
                qos=1,
                payload=json.dumps({"object":item['Name']})
            )
