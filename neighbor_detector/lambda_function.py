import boto3
import json
import base64

print('Loading function')

object_list = ['Person', 'People', 'Human']
#object_list = ['Dog', 'Canine']

def lambda_handler(event, context):
    decoded_image = base64.b64decode(event['image'])

    rekognition = boto3.client('rekognition')
    response = rekognition.detect_labels(
        Image={
            'Bytes': decoded_image,
        },
        MaxLabels=5
    )
    print(response)

    client = boto3.client('iot-data', region_name='us-east-1')

    labels = [d['Name'] for d in response['Labels']]
    labels = list(filter(lambda k: k in object_list, labels))
    print(labels)
    if len(labels):
        response = rekognition.search_faces_by_image(
                CollectionId='reinvent',
                Image={
                    'Bytes': decoded_image
                    },
                MaxFaces=1
                )

        print(response)
