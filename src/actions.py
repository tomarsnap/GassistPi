#!/usr/bin/env python

# This is different from AIY Kit's actions
# Copying and Pasting AIY Kit's actions commands will not work

from kodijson import Kodi, PLAYER_VIDEO
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauth2client.tools import argparser
from googletrans import Translator
from pushbullet import Pushbullet
from mediaplayer import api
from youtube_search_engine import google_cloud_api_key
from gtts import gTTS
from youtube_search_engine import youtube_search
from youtube_search_engine import youtube_stream_link
import requests
import mediaplayer
import os
import os.path
import RPi.GPIO as GPIO
import time
import re
import subprocess
import aftership
import feedparser
import json
import urllib.request
import pprint
import yaml

with open('/home/pi/GassistPi/src/config.yaml', 'r') as conf:
    configuration = yaml.load(conf)

# Google Music Declarations
song_ids = []
track_ids = []

# Login with default kodi/kodi credentials
# kodi = Kodi("http://localhost:8080/jsonrpc")

# Login with custom credentials
# Kodi("http://IP-ADDRESS-OF-KODI:8080/jsonrpc", "username", "password")
kodiurl = ("http://" + str(configuration['Kodi']['ip']) + ":" + str(configuration['Kodi']['port']) + "/jsonrpc")
kodi = Kodi(kodiurl, configuration['Kodi']['username'], configuration['Kodi']['password'])
musicdirectory = configuration['Kodi']['musicdirectory']
videodirectory = configuration['Kodi']['videodirectory']
windowcmd = configuration['Kodi']['windowcmd']
window = configuration['Kodi']['window']

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
# Number of entities in 'var' and 'PINS' should be the same
var = configuration['Raspberrypi_GPIO_Control']['lightnames']
gpio = configuration['Raspberrypi_GPIO_Control']['lightgpio']

# Number of station names and station links should be the same
stnname = configuration['Radio_stations']['stationnames']
stnlink = configuration['Radio_stations']['stationlinks']

# IP Address of ESP
ip = configuration['ESP']['IP']

# Declaration of ESP names
devname = configuration['ESP']['devicename']
devid = configuration['ESP']['deviceid']

for pin in gpio:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, 0)

# Servo pin declaration
GPIO.setup(27, GPIO.OUT)
pwm = GPIO.PWM(27, 50)
pwm.start(0)

# Stopbutton
GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Led Indicator
GPIO.setup(25, GPIO.OUT)
led = GPIO.PWM(25, 1)
led.start(0)

playshell = None

# Initialize colour list
clrlist = []
clrlistfullname = []
clrrgblist = []
clrhexlist = []
with open('/home/pi/GassistPi/src/colours.json', 'r') as col:
    colours = json.load(col)
for i in range(0, len(colours)):
    clrname = colours[i]["name"]
    clrnameshort = clrname.replace(" ", "", 1)
    clrnameshort = clrnameshort.strip()
    clrnameshort = clrnameshort.lower()
    clrlist.append(clrnameshort)
    clrlistfullname.append(clrname)
    clrrgblist.append(colours[i]["rgb"])
    clrhexlist.append(colours[i]["hex"])

# Parcel Tracking declarations
# If you want to use parcel tracking, register for a free account at: https://www.aftership.com
# Add the API number and uncomment next two lines
# parcelapi = aftership.APIv4('YOUR-AFTERSHIP-API-NUMBER')
# couriers = parcelapi.couriers.all.get()
number = ''
slug = ''

# RSS feed URLS
worldnews = "http://feeds.bbci.co.uk/news/world/rss.xml"
technews = "http://feeds.bbci.co.uk/news/technology/rss.xml"
topnews = "http://feeds.bbci.co.uk/news/rss.xml"
sportsnews = "http://feeds.feedburner.com/ndtvsports-latest"
quote = "http://feeds.feedburner.com/brainyquote/QUOTEBR"

##Speech and translator declarations
ttsfilename = "/tmp/say.mp3"
translator = Translator()
language = 'en'


## Other language options:
##'af'    : 'Afrikaans'         'sq' : 'Albanian'           'ar' : 'Arabic'      'hy'    : 'Armenian'
##'bn'    : 'Bengali'           'ca' : 'Catalan'            'zh' : 'Chinese'     'zh-cn' : 'Chinese (China)'
##'zh-tw' : 'Chinese (Taiwan)'  'hr' : 'Croatian'           'cs' : 'Czech'       'da'    : 'Danish'
##'nl'    : 'Dutch'             'en' : 'English'            'eo' : 'Esperanto'   'fi'    : 'Finnish'
##'fr'    : 'French'            'de' : 'German'             'el' : 'Greek'       'hi'    : 'Hindi'
##'hu'    : 'Hungarian'         'is' : 'Icelandic'          'id' : 'Indonesian'  'it'    : 'Italian'
##'ja'    : 'Japanese'          'km' : 'Khmer (Cambodian)'  'ko' : 'Korean'      'la'    : 'Latin'
##'lv'    : 'Latvian'           'mk' : 'Macedonian'         'no' : 'Norwegian'   'pl'    : 'Polish'
##'pt'    : 'Portuguese'        'ro' : 'Romanian'           'ru' : 'Russian'     'sr'    : 'Serbian'
##'si'    : 'Sinhala'           'sk' : 'Slovak'             'es' : 'Spanish'     'sw'    : 'Swahili'
##'sv'    : 'Swedish'           'ta' : 'Tamil'              'th' : 'Thai'        'tr'    : 'Turkish'
##'uk'    : 'Ukrainian'         'vi' : 'Vietnamese'         'cy' : 'Welsh'


# Function for google KS custom search engine
def kickstrater_search(query):
    service = build("customsearch", "v1",
                    developerKey=google_cloud_api_key)
    res = service.cse().list(
        q=query,
        cx='012926744822728151901:gefufijnci4',
    ).execute()
    return res


# Text to speech converter with translation
def say(words, altlang=None):
    if altlang:
        words = translator.translate(words, dest=altlang)
    else:
        words = translator.translate(words, dest=language)
    words = words.text
    words = words.replace("Text, ", '', 1)
    words = words.strip()
    print(words)
    if altlang:
        tts = gTTS(text=words, lang=altlang)
    else:
        tts = gTTS(text=words, lang=language)
    tts = gTTS(text=words, lang=language)
    tts.save(ttsfilename)
    os.system("mpg123 " + ttsfilename)
    os.remove(ttsfilename)


# Function to get HEX and RGB values for requested colour
def getcolours(phrase):
    usrclridx = idx = phrase.find("to")
    usrclr = query = phrase[usrclridx:]
    usrclr = usrclr.replace("to", "", 1)
    usrclr = usrclr.replace("'}", "", 1)
    usrclr = usrclr.strip()
    usrclr = usrclr.replace(" ", "", 1)
    usrclr = usrclr.lower()
    print(usrclr)
    try:
        for colournum, colourname in enumerate(clrlist):
            if usrclr in colourname:
                RGB = clrrgblist[colournum]
                red, blue, green = re.findall('\d+', RGB)
                hexcode = clrhexlist[colournum]
                cname = clrlistfullname[colournum]
                print(cname)
                break
        return red, blue, green, hexcode, cname
    except UnboundLocalError:
        say("Sorry unable to find a matching colour")


# Function to convert FBG to XY for Hue Lights
def convert_rgb_xy(red, green, blue):
    try:
        red = pow((red + 0.055) / (1.0 + 0.055), 2.4) if red > 0.04045 else red / 12.92
        green = pow((green + 0.055) / (1.0 + 0.055), 2.4) if green > 0.04045 else green / 12.92
        blue = pow((blue + 0.055) / (1.0 + 0.055), 2.4) if blue > 0.04045 else blue / 12.92
        X = red * 0.664511 + green * 0.154324 + blue * 0.162028
        Y = red * 0.283881 + green * 0.668433 + blue * 0.047685
        Z = red * 0.000088 + green * 0.072310 + blue * 0.986039
        x = X / (X + Y + Z)
        y = Y / (X + Y + Z)
        return x, y
    except UnboundLocalError:
        say("No RGB values given")

# ESP6266 Devcies control
def ESP(phrase):
    for num, name in enumerate(devname):
        if name.lower() in phrase:
            dev = devid[num]
            if 'on' in phrase:
                ctrl = '=ON'
                say("Turning On " + name)
            elif 'off' in phrase:
                ctrl = '=OFF'
                say("Turning Off " + name)
            rq = requests.head("https://" + ip + dev + ctrl)


# Stepper Motor control
def SetAngle(angle):
    duty = angle / 18 + 2
    GPIO.output(27, True)
    say("Moving motor by " + str(angle) + " degrees")
    pwm.ChangeDutyCycle(duty)
    time.sleep(1)
    pwm.ChangeDutyCycle(0)
    GPIO.output(27, False)


# Parcel Tracking
def track():
    text = api.trackings.get(tracking=dict(slug=slug, tracking_number=number))
    numtrack = len(text['trackings'])
    print("Total Number of Parcels: " + str(numtrack))
    if numtrack == 0:
        parcelnotify = ("You have no parcel to track")
        say(parcelnotify)
    elif numtrack == 1:
        parcelnotify = ("You have one parcel to track")
        say(parcelnotify)
    elif numtrack > 1:
        parcelnotify = ("You have " + str(numtrack) + " parcels to track")
        say(parcelnotify)
    for x in range(0, numtrack):
        numcheck = len(text['trackings'][x]['checkpoints'])
        description = text['trackings'][x]['checkpoints'][numcheck - 1]['message']
        parcelid = text['trackings'][x]['tracking_number']
        trackinfo = ("Parcel Number " + str(x + 1) + " with tracking id " + parcelid + " is " + description)
        say(trackinfo)
        # time.sleep(10)


# RSS Feed Reader
def feed(phrase):
    if 'world news' in phrase:
        URL = worldnews
    elif 'top news' in phrase:
        URL = topnews
    elif 'sports news' in phrase:
        URL = sportsnews
    elif 'tech news' in phrase:
        URL = technews
    elif 'my feed' in phrase:
        URL = quote
    numfeeds = 10
    feed = feedparser.parse(URL)
    feedlength = len(feed['entries'])
    print(feedlength)
    if feedlength < numfeeds:
        numfeeds = feedlength
    title = feed['feed']['title']
    say(title)
    # To stop the feed, press and hold stop button
    while GPIO.input(23):
        for x in range(0, numfeeds):
            content = feed['entries'][x]['title']
            print(content)
            say(content)
            summary = feed['entries'][x]['summary']
            print(summary)
            say(summary)
            if not GPIO.input(23):
                break
        if x == numfeeds - 1:
            break
        else:
            continue

# ----------Getting urls for YouTube autoplay-----------------------------------
def fetchautoplaylist(url, numvideos):
    videourl = url
    autonum = numvideos
    autoplay_urls = []
    autoplay_urls.append(videourl)
    for i in range(0, autonum):
        response = urllib.request.urlopen(videourl)
        webContent = response.read()
        webContent = webContent.decode('utf-8')
        idx = webContent.find("Up next")
        getid = webContent[idx:]
        idx = getid.find('<a href="/watch?v=')
        getid = getid[idx:]
        getid = getid.replace('<a href="/watch?v=', "", 1)
        getid = getid.strip()
        idx = getid.find('"')
        videoid = getid[:idx]
        videourl = ('https://www.youtube.com/watch?v=' + videoid)
        if not videourl in autoplay_urls:
            i = i + 1
            autoplay_urls.append(videourl)
        else:
            i = i - 1
            continue
    ##    print(autoplay_urls)
    return autoplay_urls



# -------------------Start of Kickstarter Search functions-----------------------
def campaign_page_parser(campaignname):
    page_link = kickstrater_search(campaignname)
    kicktrackurl = page_link['items'][0]['link']
    response = urllib.request.urlopen(kicktrackurl)
    webContent = response.read()
    webContent = webContent.decode('utf-8')
    return webContent


def kickstarter_get_data(page_source, parameter):
    idx = page_source.find(parameter)
    info = page_source[idx:]
    info = info.replace(parameter, "", 1)
    idx = info.find('"')
    info = info[:idx]
    info = info.replace('"', "", 1)
    info = info.strip()
    result = info
    return result


def get_campaign_title(campaign):
    campaigntitle = campaign
    campaigntitleidx1 = campaigntitle.find('<title>')
    campaigntitleidx2 = campaigntitle.find('&mdash;')
    campaigntitle = campaigntitle[campaigntitleidx1:campaigntitleidx2]
    campaigntitle = campaigntitle.replace('<title>', "", 1)
    campaigntitle = campaigntitle.replace('&mdash;', "", 1)
    campaigntitle = campaigntitle.strip()
    return campaigntitle


def get_pledges_offered(campaign):
    pledgesoffered = campaign
    pledgenum = 0
    for num in re.finditer('pledge__reward-description pledge__reward-description--expanded', pledgesoffered):
        pledgenum = pledgenum + 1
    return pledgenum


def get_funding_period(campaign):
    period = campaign
    periodidx = period.find('Funding period')
    period = period[periodidx:]
    periodidx = period.find('</p>')
    period = period[:periodidx]
    startperiodidx1 = period.find('class="invisible-if-js js-adjust-time">')
    startperiodidx2 = period.find('</time>')
    startperiod = period[startperiodidx1:startperiodidx2]
    startperiod = startperiod.replace('class="invisible-if-js js-adjust-time">', '', 1)
    startperiod = startperiod.replace('</time>', '', 1)
    startperiod = startperiod.strip()
    period2 = period[startperiodidx2 + 5:]
    endperiodidx1 = period2.find('class="invisible-if-js js-adjust-time">')
    endperiodidx2 = period2.find('</time>')
    endperiod = period2[endperiodidx1:endperiodidx2]
    endperiod = endperiod.replace('class="invisible-if-js js-adjust-time">', '', 1)
    endperiod = endperiod.replace('</time>', '', 1)
    endperiod = endperiod.strip()
    duration = period2[endperiodidx2:]
    duration = duration.replace('</time>', '', 1)
    duration = duration.replace('(', '', 1)
    duration = duration.replace(')', '', 1)
    duration = duration.replace('days', 'day', 1)
    duration = duration.strip()
    return startperiod, endperiod, duration


def kickstarter_tracker(phrase):
    idx = phrase.find('of')
    campaign_name = phrase[idx:]
    campaign_name = campaign_name.replace("kickstarter campaign", "", 1)
    campaign_name = campaign_name.replace('of', '', 1)
    campaign_name = campaign_name.strip()
    campaign_source = campaign_page_parser(campaign_name)
    campaign_title = get_campaign_title(campaign_source)
    campaign_num_rewards = get_pledges_offered(campaign_source)
    successidx = campaign_source.find('to help bring this project to life.')
    if str(successidx) == str(-1):
        backers = kickstarter_get_data(campaign_source, 'data-backers-count="')
        totalpledged = kickstarter_get_data(campaign_source, 'data-pledged="')
        totaltimerem = kickstarter_get_data(campaign_source, 'data-hours-remaining="')
        totaldur = kickstarter_get_data(campaign_source, 'data-duration="')
        endtime = kickstarter_get_data(campaign_source, 'data-end_time="')
        goal = kickstarter_get_data(campaign_source, 'data-goal="')
        percentraised = kickstarter_get_data(campaign_source, 'data-percent-raised="')
        percentraised = round(float(percentraised), 2)
        if int(totaltimerem) > 0:
            # print(campaign_title+" is an ongoing campaign with "+str(totaltimerem)+" hours of fundraising still left." )
            say(campaign_title + " is an ongoing campaign with " + str(
                totaltimerem) + " hours of fundraising still left.")
            # print("Till now, "+str(backers)+ " backers have pledged for "+str(campaign_num_rewards)+" diferent rewards raising $"+str(totalpledged)+" , which is "+str(percentraised)+" times the requested amount of $"+str(goal))
            say("Till now, " + str(backers) + " backers have pledged for " + str(
                campaign_num_rewards) + " diferent rewards raising $" + str(totalpledged) + " , which is " + str(
                percentraised) + " times the requested amount of $" + str(goal))
        if float(percentraised) < 1 and int(totaltimerem) <= 0:
            # print(campaign_title+" has already ended")
            say(campaign_title + " has already ended")
            # print(str(backers)+ " backers raised $"+str(totalpledged)+" , which was "+str(percentraised)+" times the requested amount of $"+str(goal))
            say(str(backers) + " backers raised $" + str(totalpledged) + " , which was " + str(
                percentraised) + " times the requested amount of $" + str(goal))
            # print(campaign_title+" was unseccessful in raising the requested amount of $"+str(goal)+" ." )
            say(campaign_title + " was unseccessful in raising the requested amount of $" + str(goal) + " .")
        if float(percentraised) > 1 and int(totaltimerem) <= 0:
            # print(campaign_title+" has already ended")
            say(campaign_title + " has already ended")
            # print(str(backers)+ " backers raised $"+str(totalpledged)+" , which was "+str(percentraised)+" times the requested amount of $"+str(goal))
            say(str(backers) + " backers raised $" + str(totalpledged) + " , which was " + str(
                percentraised) + " times the requested amount of $" + str(goal))
            # print("Though the funding goal was reached, due to reasons undisclosed, the campaign was either cancelled by the creator or Kickstarter.")
            say(
                "Though the funding goal was reached, due to reasons undisclosed, the campaign was either cancelled by the creator or Kickstarter.")
    else:
        [start_day, end_day, numdays] = get_funding_period(campaign_source)
        campaigninfo = campaign_source[(successidx - 100):(successidx + 35)]
        campaignidx = campaigninfo.find('<b>')
        campaigninfo = campaigninfo[campaignidx:]
        campaigninfo = campaigninfo.replace('<b>', "", 1)
        campaigninfo = campaigninfo.replace('</b>', "", 1)
        campaigninfo = campaigninfo.replace('<span class="money">', "", 1)
        campaigninfo = campaigninfo.replace('</span>', "", 1)
        campaigninfo = campaigninfo.strip()
        # print(campaign_title+" was a "+str(numdays)+" campaign launched on "+str(start_day))
        # print(campaigninfo)
        say(campaign_title + " was a " + str(numdays) + " campaign launched on " + str(start_day))
        say(campaigninfo)


# ------------------------------End of Kickstarter Search functions---------------------------------------


# ----------------------------------Start of Push Message function-----------------------------------------
def pushmessage(title, body):
    pb = Pushbullet('ENTER-YOUR-PUSHBULLET-KEY-HERE')
    push = pb.push_note(title, body)


# ----------------------------------End of Push Message Function-------------------------------------------


# ----------------------------------Start of recipe Function----------------------------------------------
def getrecipe(item):
    appid = 'ENTER-YOUR-APPID-HERE'
    appkey = 'ENTER-YOUR-APP-KEY-HERE'
    recipeurl = 'https://api.edamam.com/search?q=' + item + '&app_id=' + appid + '&app_key=' + appkey
    print(recipeurl)
    recipedetails = urllib.request.urlopen(recipeurl)
    recipedetails = recipedetails.read()
    recipedetails = recipedetails.decode('utf-8')
    recipedetails = json.loads(recipedetails)
    recipe_ingredients = str(recipedetails['hits'][0]['recipe']['ingredientLines'])
    recipe_url = recipedetails['hits'][0]['recipe']['url']
    recipe_name = recipedetails['hits'][0]['recipe']['label']
    recipe_ingredients = recipe_ingredients.replace('[', '', 1)
    recipe_ingredients = recipe_ingredients.replace(']', '', 1)
    recipe_ingredients = recipe_ingredients.replace('"', '', 1)
    recipe_ingredients = recipe_ingredients.strip()
    print(recipe_name)
    print("")
    print(recipe_url)
    print("")
    print(recipe_ingredients)
    compiled_recipe_info = "\nRecipe Source URL:\n" + recipe_url + "\n\nRecipe Ingredients:\n" + recipe_ingredients
    pushmessage(str(recipe_name), str(compiled_recipe_info))


# ---------------------------------End of recipe Function------------------------------------------------


# --------------------------------Start of Hue Control Functions------------------------------------------

def hue_control(phrase, lightindex, lightaddress):
    with open('/home/pi/GassistPi/src/diyHue/config.json', 'r') as config:
        hueconfig = json.load(config)
    currentxval = hueconfig['lights'][lightindex]['state']['xy'][0]
    currentyval = hueconfig['lights'][lightindex]['state']['xy'][1]
    currentbri = hueconfig['lights'][lightindex]['state']['bri']
    currentct = hueconfig['lights'][lightindex]['state']['ct']
    huelightname = str(hueconfig['lights'][lightindex]['name'])
    try:
        if 'on' in phrase:
            huereq = requests.head("http://" + lightaddress + "/set?light=" + lightindex + "&on=true")
            say("Turning on " + huelightname)
        if 'off' in phrase:
            huereq = requests.head("http://" + lightaddress + "/set?light=" + lightindex + "&on=false")
            say("Turning off " + huelightname)
        if 'çolor' in phrase:
            rcolour, gcolour, bcolour, hexcolour, colour = getcolours(phrase)
            print(str([rcolour, gcolour, bcolour, hexcolour, colour]))
            xval, yval = convert_rgb_xy(int(rcolour), int(gcolour), int(bcolour))
            print(str([xval, yval]))
            huereq = requests.head(
                "http://" + lightaddress + "/set?light=" + lightindex + "&x=" + str(xval) + "&y=" + str(
                    yval) + "&on=true")
            print("http://" + lightaddress + "/set?light=" + lightindex + "&x=" + str(xval) + "&y=" + str(
                yval) + "&on=true")
            say("Setting " + huelightname + " to " + colour)
        if 'brightness'.lower() in phrase:
            if 'hundred'.lower() in str(usrcmd).lower() or 'maximum' in str(usrcmd).lower():
                bright = 100
            elif 'zero'.lower() in str(usrcmd).lower() or 'minimum' in str(usrcmd).lower():
                bright = 100
            else:
                bright = re.findall('\d+', phrase)
            brightval = (bright / 100) * 255
            huereq = requests.head(
                "http://" + lightaddress + "/set?light=" + lightindex + "&on=true&bri=" + str(brightval))
            say("Changing " + huelightname + " brightness to " + bright + " percent")
    except (requests.exceptions.ConnectionError, TypeError) as errors:
        if str(errors) == "'NoneType' object is not iterable":
            print("Type Error")
        else:
            say("Device not online")


# ------------------------------End of Hue Control Functions---------------------------------------------


# GPIO Device Control
def Action(phrase):
    if 'shut down' in phrase:
        say('Shutting down Raspberry Pi')
        time.sleep(10)
        os.system("sudo shutdown -h now")
        # subprocess.call(["shutdown -h now"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if 'servo' in phrase:
        for s in re.findall(r'\b\d+\b', phrase):
            SetAngle(int(s))
    if 'zero' in phrase:
        SetAngle(0)
    else:
        for num, name in enumerate(var):
            if name.lower() in phrase:
                pinout = gpio[num]
                if 'on' in phrase:
                    GPIO.output(pinout, 1)
                    say("Turning On " + name)
                elif 'off' in phrase:
                    GPIO.output(pinout, 0)
                    say("Turning Off " + name)
