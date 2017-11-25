import base64
import boto3
import json
import logging

object_list = ['Dog', 'Canine']

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    client = boto3.client('rekognition')

    response = client.detect_labels(
        Image={
            'Bytes': base64.b64decode(event['image']),
        },
        MaxLabels=5
    )

    logger.info(response)

    client = boto3.client('iot-data', region_name='us-east-1')

    for item in response['Labels']:
        if item['Name'] in object_list:
            # Change topic, qos and payload
            response = client.publish(
                topic='sdk/objectDetected',
                qos=1,
                payload=json.dumps({"object":item['Name']})
            )

