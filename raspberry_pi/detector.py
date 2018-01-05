
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import logging
import time
import argparse
import io
import os
import json
import base64
import boto3
from subprocess import call

import threading

need_capture = False

def write_now():
    global need_capture
    if need_capture == True:
        need_capture = False
        return True
    return need_capture

def write_video(stream):
    try:
        os.remove('motion.h264')
        os.remove('motion.mp4')
    except:
        print("motion.h264 does not exist")

    print('Writing video!')
    client = boto3.client('s3')
    with stream.lock:
        # Find the first header frame in the video
        for frame in stream.frames:
            if frame.frame_type == picamera.PiVideoFrameType.sps_header:
                stream.seek(frame.position)
                break

        with io.open('motion.h264', 'wb') as output:
            output.write(stream.read())
        data = open('motion.h264', 'rb')
        # Write the rest of the stream to disk
        client.put_object(
            Body=data,
            Bucket='iot-rekognition',
            Key=str(time.time()) + '.h264'
        )


# General message notification callback
def customOnMessage(message):
    global need_capture
    if message.topic == "sdk/objectDetected":
        need_capture = True
    print("Received a new message: ")
    print(message.payload)
    print("from topic: ")
    print(message.topic)
    print("--------------\n\n")


# Suback callback
def customSubackCallback(mid, data):
    print("Received SUBACK packet id: ")
    print(mid)
    print("Granted QoS: ")
    print(data)
    print("++++++++++++++\n\n")


# Puback callback
def customPubackCallback(mid):
    print("Received PUBACK packet id: ")
    print(mid)
    print("++++++++++++++\n\n")


# Read in command-line parameters
parser = argparse.ArgumentParser()
parser.add_argument("-e", "--endpoint", action="store", required=True, dest="host", help="Your AWS IoT custom endpoint")
parser.add_argument("-r", "--rootCA", action="store", required=True, dest="rootCAPath", help="Root CA file path")
parser.add_argument("-c", "--cert", action="store", dest="certificatePath", help="Certificate file path")
parser.add_argument("-k", "--key", action="store", dest="privateKeyPath", help="Private key file path")
parser.add_argument("-w", "--websocket", action="store_true", dest="useWebsocket", default=False,
                    help="Use MQTT over WebSocket")
parser.add_argument("-id", "--clientId", action="store", dest="clientId", default="basicPubSub",
                    help="Targeted client id")
parser.add_argument("-t", "--topic", action="store", dest="topic", default="sdk/test/Python", help="Targeted topic")

args = parser.parse_args()
host = args.host
rootCAPath = args.rootCAPath
certificatePath = args.certificatePath
privateKeyPath = args.privateKeyPath
useWebsocket = args.useWebsocket
clientId = args.clientId
topic = args.topic

if args.useWebsocket and args.certificatePath and args.privateKeyPath:
    parser.error("X.509 cert authentication and WebSocket are mutual exclusive. Please pick one.")
    exit(2)

if not args.useWebsocket and (not args.certificatePath or not args.privateKeyPath):
    parser.error("Missing credentials for authentication.")
    exit(2)

# Configure logging
logger = logging.getLogger("AWSIoTPythonSDK.core")
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

# Init AWSIoTMQTTClient
myAWSIoTMQTTClient = None
if useWebsocket:
    myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId, useWebsocket=True)
    myAWSIoTMQTTClient.configureEndpoint(host, 443)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath)
else:
    myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
    myAWSIoTMQTTClient.configureEndpoint(host, 8883)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

# AWSIoTMQTTClient connection configuration
myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myAWSIoTMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
myAWSIoTMQTTClient.onMessage = customOnMessage

# Connect and subscribe to AWS IoT
myAWSIoTMQTTClient.connect()
# Note that we are not putting a message callback here. We are using the general message notification callback.
myAWSIoTMQTTClient.subscribeAsync(topic, 1, ackCallback=customSubackCallback)
myAWSIoTMQTTClient.subscribeAsync("sdk/objectDetected", 1, ackCallback=customSubackCallback)

time.sleep(2)


import picamera
import picamera.array
import numpy as np
import datetime

class MotionDetector(picamera.array.PiMotionAnalysis):
    def __init__(self, camera, size=None):
        super(MotionDetector, self).__init__(camera, size)
        self.latest_event = datetime.datetime.now()
        self.camera = camera

    def ship_frame(self):
        outstanding_request = True
        my_stream = io.BytesIO()
        self.camera.capture(my_stream, 'jpeg', quality=10)
        data = {}
        encoded_string = base64.b64encode(my_stream.getvalue())
        data['image'] = str(bytes.decode(encoded_string))
        myAWSIoTMQTTClient.publishAsync('sdk/images', str(json.dumps(data)), 1, ackCallback=customPubackCallback)


    def analyse(self, a):
        a = np.sqrt(
            np.square(a['x'].astype(np.float)) +
            np.square(a['y'].astype(np.float))
            ).clip(0, 255).astype(np.uint8)
        # If there're more than 10 vectors with a magnitude greater
        # than 60, then say we've detected motion
        if (a > 20).sum() > 10:
            if (datetime.datetime.now() - self.latest_event).total_seconds() > 3:
                myAWSIoTMQTTClient.publishAsync(topic, "Detected Motion", 1, ackCallback=customPubackCallback)
                self.ship_frame()
                print('Motion detected!')
                self.latest_event = datetime.datetime.now()


with picamera.PiCamera() as camera:
    latest_event = datetime.datetime.now()
    camera.resolution = (1280, 720)
    camera.framerate = 20
    camera.rotation = 270
    stream = picamera.PiCameraCircularIO(camera, seconds=5)

    camera.start_recording(
        stream, format='h264',
        motion_output=MotionDetector(camera)
        )

    try:
        while True:
            camera.wait_recording(1)
            if write_now():
                camera.wait_recording(5)
                t = threading.Thread(target=write_video, args=(stream,))
                t.start()
    finally:
        camera.stop_recording()
