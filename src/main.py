#!/usr/bin/env python
# coding=utf-8

# Copyright (C) 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function
import RPi.GPIO as GPIO
import argparse
import json
import os.path
import pathlib2 as pathlib
import os
import subprocess
import re
import psutil
import logging
import google.oauth2.credentials
from google.assistant.library import Assistant
from google.assistant.library.event import EventType
from google.assistant.library.file_helpers import existing_file
from google.assistant.library.device_helpers import register_device
from actions import say
from actions import Action
from actions import ESP
from actions import track
from actions import feed
import requests
from actions import kickstarter_tracker
from actions import getrecipe
from actions import hue_control
from actions import configuration

try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError


WARNING_NOT_REGISTERED = """
    This device is not registered. This means you will not be able to use
    Device Actions or see your device in Assistant Settings. In order to
    register this device follow instructions at:

    https://developers.google.com/assistant/sdk/guides/library/python/embed/register-device
"""

logging.basicConfig(filename='/tmp/GassistPi.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

#Indicator Pins
GPIO.setup(25, GPIO.OUT)
GPIO.setup(5, GPIO.OUT)
GPIO.setup(6, GPIO.OUT)
GPIO.output(5, GPIO.LOW)
GPIO.output(6, GPIO.LOW)
led=GPIO.PWM(25,1)
led.start(0)




#Sonoff-Tasmota Declarations
#Make sure that the device name assigned here does not overlap any of your smart device names in the google home app
tasmota_devicelist=configuration['Tasmota_devicelist']['friendly-names']
tasmota_deviceip=configuration['Tasmota_devicelist']['ipaddresses']

#Magic Mirror Remote Control Declarations
mmmip=configuration['Mmmip']


#Function to control Sonoff Tasmota Devices
def tasmota_control(phrase,devname,devip):
    try:
        if 'on' in phrase:
            rq=requests.head("http://"+devip+"/cm?cmnd=Power%20on")
            say("Tunring on "+devname)
        elif 'off' in phrase:
            rq=requests.head("http://"+devip+"/cm?cmnd=Power%20off")
            say("Tunring off "+devname)
    except requests.exceptions.ConnectionError:
        say("Device not online")

def process_device_actions(event, device_id):
    if 'inputs' in event.args:
        for i in event.args['inputs']:
            if i['intent'] == 'action.devices.EXECUTE':
                for c in i['payload']['commands']:
                    for device in c['devices']:
                        if device['id'] == device_id:
                            if 'execution' in c:
                                for e in c['execution']:
                                    if 'params' in e:
                                        yield e['command'], e['params']
                                    else:
                                        yield e['command'], None


def process_event(event):
    """Pretty prints events.
    Prints all events that occur with two spaces between each new
    conversation and a single space between turns of a conversation.
    Args:
        event(event.Event): The current event to process.
    """
    if event.type == EventType.ON_CONVERSATION_TURN_STARTED:
        subprocess.Popen(["aplay", "/home/pi/GassistPi/sample-audio-files/Fb.wav"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        #Uncomment the following after starting the Kodi
        #status=mutevolstatus()
        #vollevel=status[1]
        #with open('/home/pi/.volume.json', 'w') as f:
               #json.dump(vollevel, f)
        #kodi.Application.SetVolume({"volume": 0})
        GPIO.output(5,GPIO.HIGH)
        led.ChangeDutyCycle(100)
        print()



    if event.type == EventType.ON_CONVERSATION_TURN_TIMEOUT:
      GPIO.output(5,GPIO.LOW)
      GPIO.output(6,GPIO.LOW)
      led.ChangeDutyCycle(0)

    if (event.type == EventType.ON_RESPONDING_STARTED and event.args and not event.args['is_error_response']):
       GPIO.output(5,GPIO.LOW)
       GPIO.output(6,GPIO.HIGH)
       led.ChangeDutyCycle(50)

    if event.type == EventType.ON_RESPONDING_FINISHED:
       GPIO.output(6,GPIO.LOW)
       GPIO.output(5,GPIO.LOW)
       led.ChangeDutyCycle(0)

    if event.type == EventType.ON_RECOGNIZING_SPEECH_FINISHED:
       GPIO.output (5, GPIO.LOW)
       GPIO.output (6, GPIO.LOW)
       led.ChangeDutyCycle (0)

    print(event)

    if (event.type == EventType.ON_CONVERSATION_TURN_FINISHED and
            event.args and not event.args['with_follow_on_turn']):
        GPIO.output(5,GPIO.LOW)
        GPIO.output(6,GPIO.LOW)
        led.ChangeDutyCycle(0)
        print()

    if event.type == EventType.ON_DEVICE_ACTION:
        for command, params in event.actions:
            print('Do command', command, 'with params', str(params))

def register_device(project_id, credentials, device_model_id, device_id):
    """Register the device if needed.
    Registers a new assistant device if an instance with the given id
    does not already exists for this model.
    Args:
       project_id(str): The project ID used to register device instance.
       credentials(google.oauth2.credentials.Credentials): The Google
                OAuth2 credentials of the user to associate the device
                instance with.
       device_model_id: The registered device model ID.
       device_id: The device ID of the new instance.
    """
    base_url = '/'.join([DEVICE_API_URL, 'projects', project_id, 'devices'])
    device_url = '/'.join([base_url, device_id])
    session = google.auth.transport.requests.AuthorizedSession(credentials)
    r = session.get(device_url)
    print(device_url, r.status_code)
    if r.status_code == 404:
        print('Registering....')
        r = session.post(base_url, data=json.dumps({
            'id': device_id,
            'model_id': device_model_id,
            'client_type': 'SDK_LIBRARY'
        }))
        if r.status_code != 200:
            raise Exception('failed to register device: ' + r.text)
        print('\rDevice registered.')


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--device-model-id', '--device_model_id', type=str,
                        metavar='DEVICE_MODEL_ID', required=False,
                        help='the device model ID registered with Google')
    parser.add_argument('--project-id', '--project_id', type=str,
                        metavar='PROJECT_ID', required=False,
                        help='the project ID used to register this device')
    parser.add_argument('--device-config', type=str,
                        metavar='DEVICE_CONFIG_FILE',
                        default=os.path.join(
                            os.path.expanduser('~/.config'),
                            'googlesamples-assistant',
                            'device_config_library.json'
                        ),
                        help='path to store and read device configuration')
    parser.add_argument('--credentials', type=existing_file,
                        metavar='OAUTH2_CREDENTIALS_FILE',
                        default=os.path.join(
                            os.path.expanduser('~/.config'),
                            'google-oauthlib-tool',
                            'credentials.json'
                        ),
                        help='path to store and read OAuth2 credentials')
    parser.add_argument('-v', '--version', action='version',
                        version='%(prog)s ' + Assistant.__version_str__())

    args = parser.parse_args()
    with open(args.credentials, 'r') as f:
        credentials = google.oauth2.credentials.Credentials(token=None,
                                                            **json.load(f))

    device_model_id = None
    last_device_id = None
    try:
        with open(args.device_config) as f:
            device_config = json.load(f)
            device_model_id = device_config['model_id']
            last_device_id = device_config.get('last_device_id', None)
    except FileNotFoundError:
        pass

    if not args.device_model_id and not device_model_id:
        raise Exception('Missing --device-model-id option')

    # Re-register if "device_model_id" is given by the user and it differs
    # from what we previously registered with.
    should_register = (
        args.device_model_id and args.device_model_id != device_model_id)

    device_model_id = args.device_model_id or device_model_id
    with Assistant(credentials, device_model_id) as assistant:
        subprocess.Popen(["aplay", "/home/pi/GassistPi/sample-audio-files/Startup.wav"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        events = assistant.start()

        device_id = assistant.device_id
        print('device_model_id:', device_model_id)
        print('device_id:', device_id + '\n')

        # Re-register if "device_id" is different from the last "device_id":
        if should_register or (device_id != last_device_id):
            if args.project_id:
                register_device(args.project_id, credentials,
                                device_model_id, device_id)
                pathlib.Path(os.path.dirname(args.device_config)).mkdir(
                    exist_ok=True)
                with open(args.device_config, 'w') as f:
                    json.dump({
                        'last_device_id': device_id,
                        'model_id': device_model_id,
                    }, f)
            else:
                print(WARNING_NOT_REGISTERED)

        for event in events:
            process_event(event)
            usrcmd=event.args
            with open('/home/pi/GassistPi/src/diyHue/config.json', 'r') as config:
                 hueconfig = json.load(config)
            for i in range(1,len(hueconfig['lights'])+1):
                try:
                    if str(hueconfig['lights'][str(i)]['name']).lower() in str(usrcmd).lower():
                        assistant.stop_conversation()
                        hue_control(str(usrcmd).lower(),str(i),str(hueconfig['lights_address'][str(i)]['ip']))
                        break
                except KeyError:
                    say('Unable to help, please check your config file')

            for num, name in enumerate(tasmota_devicelist):
                if name.lower() in str(usrcmd).lower():
                    assistant.stop_conversation()
                    tasmota_control(str(usrcmd).lower(), name.lower(),tasmota_deviceip[num])
                    break
            if 'magic mirror'.lower() in str(usrcmd).lower():
                assistant.stop_conversation()
                try:
                    mmmcommand=str(usrcmd).lower()
                    if 'weather'.lower() in mmmcommand:
                        if 'show'.lower() in mmmcommand:
                            mmreq_one=requests.get("http://"+mmmip+":8080/remote?action=SHOW&module=module_2_currentweather")
                            mmreq_two=requests.get("http://"+mmmip+":8080/remote?action=SHOW&module=module_3_currentweather")
                        if 'hide'.lower() in mmmcommand:
                            mmreq_one=requests.get("http://"+mmmip+":8080/remote?action=HIDE&module=module_2_currentweather")
                            mmreq_two=requests.get("http://"+mmmip+":8080/remote?action=HIDE&module=module_3_currentweather")
                    if 'power off'.lower() in mmmcommand:
                        mmreq=requests.get("http://"+mmmip+":8080/remote?action=SHUTDOWN")
                    if 'reboot'.lower() in mmmcommand:
                        mmreq=requests.get("http://"+mmmip+":8080/remote?action=REBOOT")
                    if 'restart'.lower() in mmmcommand:
                        mmreq=requests.get("http://"+mmmip+":8080/remote?action=RESTART")
                    if 'display on'.lower() in mmmcommand:
                        mmreq=requests.get("http://"+mmmip+":8080/remote?action=MONITORON")
                    if 'display off'.lower() in mmmcommand:
                        mmreq=requests.get("http://"+mmmip+":8080/remote?action=MONITOROFF")
                except requests.exceptions.ConnectionError:
                    say("Magic mirror not online")
            if 'ingredients'.lower() in str(usrcmd).lower():
                assistant.stop_conversation()
                ingrequest=str(usrcmd).lower()
                ingredientsidx=ingrequest.find('for')
                ingrequest=ingrequest[ingredientsidx:]
                ingrequest=ingrequest.replace('for',"",1)
                ingrequest=ingrequest.replace("'}","",1)
                ingrequest=ingrequest.strip()
                ingrequest=ingrequest.replace(" ","%20",1)
                getrecipe(ingrequest)
            if 'kickstarter'.lower() in str(usrcmd).lower():
                assistant.stop_conversation()
                kickstarter_tracker(str(usrcmd).lower())
            if 'trigger'.lower() in str(usrcmd).lower():
                assistant.stop_conversation()
                Action(str(usrcmd).lower())
            if 'wireless'.lower() in str(usrcmd).lower():
                assistant.stop_conversation()
                ESP(str(usrcmd).lower())
            if 'parcel'.lower() in str(usrcmd).lower():
                assistant.stop_conversation()
                track()
            if 'news'.lower() in str(usrcmd).lower() or 'feed'.lower() in str(usrcmd).lower() or 'quote'.lower() in str(usrcmd).lower():
                assistant.stop_conversation()
                feed(str(usrcmd).lower())
            if 'update'.lower() in str(usrcmd).lower():
                assistant.stop_conversation()
                if 'magic mirror'.lower() in str(usrcmd).lower():
                    # update magic mirror also
                    pass
                say("Päivitetään", "fi")
                subprocess.Popen(["sudo systemctl stop gassistpi-ok-google && git -C /home/pi/GassistPi pull "
                                  "&& sudo systemctl start gassistpi-ok-google"], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        logger.exception(error)
