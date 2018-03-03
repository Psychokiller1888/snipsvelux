#!/usr/bin/python
# -*- coding: utf-8 -*-

# 2018 - Psychokiller1888 / Laurent Chervet
# If you find any bugs, please report on github
# If reusing keep credits

import json
import math
import paho.mqtt.client as mqtt
import RPi.GPIO as gpio
import time
import threading

###### REMOTE BUTTON SCHEME ######
# ----------
# | SCREEN |
# |        |
# ----------
# 1 - 2 - 3
# 4 - 5 - 6
#     7
#
#     8
#
#     9
#
#
#         10
#
# 1 = menu
# 2 = up arrow
# 3 = back
# 4 = p1
# 5 = down arrow
# 6 = p2
# 7 = up
# 8 = stop
# 9 = down
# 10 = reset (back side)
#
# Make sure you don't have any registered program!
# Make sure to turn off screen saving so the remote doesn't need waking up
# On start wait 12 seconds for booting

_RUNNING 		= True


_MENU_PIN		= 33
_UP_ARROW_PIN	= 32
_BACK_PIN		= 31
_DOWN_ARROW_PIN = 36
_UP_PIN 		= 35
_STOP_PIN 		= 38
_DOWN_PIN 		= 37
_RESET_PIN 		= 40
_POWER_ON_PIN 	= 26


# Defines button press per actions
# Insert a string to add a pause after button click exemple: ['1', 3, 1] Would wait 1 seconds after each button click. Default wait time is 0.5
_COMMANDS = {
	'open': 					[7],
	'close': 					[9],
	'fullOpen': 				[7, 7],
	'fullClose': 				[9, 9],
	'selectAllWindows': 		['1.25', 3, '0.25', 1, 1,],
	'selectAllBlinders': 		['1.25', 3, '0.25', 1, 5, 1]
	#'selectBedroomWindows': 	['1.25', 3, '0.25', 5, 1, 1, 5, 5, 1],
	#'selectBathroomWindows': 	['1.25', 3, '0.25', 5, 5, 5, 1],
	#'selectRoomWindows': 		['1.25', 3, '0.25', 5, 5, 1, 5, 5, 1],
	#'selectBedroomBlinders': 	['1.25', 3, '0.25', 5, 1, 5, 1, 5, 5, 1],
}

#_INTENT_OPEN_WINDOWS	= 'hermes/intent/Psychokiller1888:openVelux'
#_INTENT_CLOSE_WINDOWS	= 'hermes/intent/Psychokiller1888:closeVelux'
#_INTENT_OPEN_BLINDERS	= 'hermes/intent/Psychokiller1888:openBlinders'
#_INTENT_CLOSE_BLINDERS	= 'hermes/intent/Psychokiller1888:closeBlinders'

_INTENT_OPEN_WINDOWS	= 'projectAlice/intent/velux/open'
_INTENT_CLOSE_WINDOWS	= 'projectAlice/intent/velux/close'
_INTENT_OPEN_BLINDERS	= 'projectAlice/intent/velux/openBlinders'
_INTENT_CLOSE_BLINDERS	= 'projectAlice/intent/velux/closeBlinders'

_ready = False
_thread = None
_closingThreads = {}

def onConnect(client, userdata, flags, rc):
	_mqttClient.subscribe(_INTENT_OPEN_WINDOWS)
	_mqttClient.subscribe(_INTENT_CLOSE_WINDOWS)
	_mqttClient.subscribe(_INTENT_OPEN_BLINDERS)
	_mqttClient.subscribe(_INTENT_CLOSE_BLINDERS)

def onMessage(client, userdata, message):
	global _ready

	if not _ready:
		return

	payload = json.loads(message.payload)

	if message.topic == _INTENT_OPEN_WINDOWS:
		duration = 0
		if 'duration' in payload and payload['duration'] != 0:
			duration = payload['duration']['duration']

		percentage = 'full'
		if 'percentage' in payload and payload['percentage'] != 'full':
			percentage = payload['percentage'].replace('%', '')
			percentage = int(math.ceil(int(percentage) / 10.0)) * 10

		place = 'all'
		if 'place' in payload and payload['place'] != 'all':
			place = payload['place']

		if place == 'second room':
			place = 'room'

		if percentage != 'full':
			openToCertainPercentage(percent=percentage, windows=place, duration=duration)
		else:
			fullOpen(what='windows', which=place, duration=duration)

		print('Opening windows (Payload was {})'.format(payload))
	elif message.topic == _INTENT_CLOSE_WINDOWS:
		when = 0
		if 'when' in payload and payload['when'] != 0:
			when = payload['when']['duration']

		place = 'all'
		if 'place' in payload and payload['place'] != 'all':
			place = payload['place']

		if when == 0:
			fullClose(what='windows', which=place)
		else:
			thread = threading.Timer(when, fullClose, ['windows', place])
			thread.start()
		print('Closing windows (Payload was {})'.format(payload))
	elif message.topic == _INTENT_OPEN_BLINDERS:
		percentage = 'full'
		if 'percentage' in payload and payload['percentage'] != 'full':
			percentage = payload['percentage'].replace('%', '')
			percentage = int(math.ceil(int(percentage) / 10.0)) * 10

		place = 'all'
		if 'place' in payload and payload['place'] != 'all':
			place = payload['place']

		if percentage != 'full':
			openBlindersToCertainPercentage(percent=percentage, blinders=place)
		else:
			fullOpen(what='blinders', which=place)

		print('Opening blinders (Payload was {})'.format(payload))
	elif message.topic == _INTENT_CLOSE_BLINDERS:
		percentage = 'full'
		if 'percentage' in payload and payload['percentage'] != 'full':
			percentage = payload['percentage'].replace('%', '')
			percentage = int(math.ceil(int(percentage) / 10.0)) * 10

		place = 'all'
		if 'place' in payload and payload['place'] != 'all':
			place = payload['place']

		if percentage != 'full':
			openBlindersToCertainPercentage(percent=percentage, blinders=place)
		else:
			fullClose(what='blinders', which=place)

			print('Closing blinders (Payload was {})'.format(payload))

def stop():
	global _RUNNING
	_RUNNING = False

def fullOpen(what='windows', which='all', duration=0):
	global _COMMANDS
	str = 'select{}{}'.format(which.title(), what.title())
	if str not in _COMMANDS:
		str = 'selectAllWindows'

	executeCommand(_COMMANDS[str])
	executeCommand(_COMMANDS['fullOpen'])
	if what == 'windows' and duration > 0:
		thread = threading.Timer(duration, fullClose, ['windows', 'all'])
		thread.start()

def fullClose(what='windows', which='all'):
	global _COMMANDS
	str = 'select{}{}'.format(which.title(), what.title())
	if str not in _COMMANDS:
		str = 'selectAllWindows'
	executeCommand(_COMMANDS[str])
	executeCommand(_COMMANDS['fullClose'])


def openToCertainPercentage(percent, windows='all', duration=0):
	global _COMMANDS

	if percent == 0:
		fullClose(what='windows', which=windows)
		return
	elif percent == 10:
		timer = 3.3
	elif percent == 20:
		timer = 4.1
	elif percent == 30:
		timer = 4.8
	elif percent == 40:
		timer = 5.3
	elif percent == 50:
		timer = 6
	elif percent == 60:
		timer = 6.8
	elif percent == 70:
		timer = 7.4
	elif percent == 80:
		timer = 8.1
	elif percent == 90:
		timer = 8.8
	else:
		fullOpen(what='windows', which=windows, duration=duration)
		return

	executeCommand(_COMMANDS['select{}Windows'.format(windows.title())])
	executeCommand(_COMMANDS['open'], clickTime=timer)

	if duration > 0:
		thread = threading.Timer(duration, fullClose, ['windows', windows])
		thread.start()

def openBlindersToCertainPercentage(percent, blinders='all'):
	global _COMMANDS

	if percent == 0:
		fullClose(what='blinders', which=blinders)
		return
	elif percent == 10:
		timer = 1.8
	elif percent == 20:
		timer = 2.4
	elif percent == 30:
		timer = 3
	elif percent == 40:
		timer = 3.7
	elif percent == 50:
		timer = 4.6
	elif percent == 60:
		timer = 5.1
	elif percent == 70:
		timer = 5.8
	elif percent == 80:
		timer = 6.5
	elif percent == 90:
		timer = 7.3
	else:
		fullOpen(what='blinders', which=blinders)
		return

	executeCommand(_COMMANDS['select{}Blinders'.format(blinders.title())])
	executeCommand(_COMMANDS['close'], clickTime=timer)

def executeCommand(commandList, clickTime=0.2):
	global _ready
	_ready = False

	waitTime = 0.5
	for cmd in commandList:
		if isinstance(cmd, basestring):
			waitTime = float(cmd)
			continue

		pin = translateButton(cmd)
		if pin == -1:
			break
		gpio.output(pin, gpio.HIGH)
		time.sleep(clickTime)
		gpio.output(pin, gpio.LOW)
		time.sleep(waitTime)

	_ready = True

def translateButton(buttonNumber):
	if buttonNumber == 1:
		return _MENU_PIN
	elif buttonNumber == 2:
		return _UP_ARROW_PIN
	elif buttonNumber == 3:
		return _BACK_PIN
	elif buttonNumber == 5:
		return _DOWN_ARROW_PIN
	elif buttonNumber == 7:
		return _UP_PIN
	elif buttonNumber == 8:
		return _STOP_PIN
	elif buttonNumber == 9:
		return _DOWN_PIN
	elif buttonNumber == 10:
		return _RESET_PIN
	else:
		print('Unknown button: ' + str(buttonNumber))
		return -1

def powerOn():
	global _ready
	_ready = False
	gpio.output(_POWER_ON_PIN, gpio.HIGH)
	threading.Timer(12, onRemoteStarted).start()

def onRemoteStarted():
	global _ready
	_ready = True
	print('Module ready')

def setupGpio():
	gpio.setmode(gpio.BOARD)
	gpio.setwarnings(False)
	gpio.setup(_MENU_PIN, gpio.OUT, gpio.PUD_OFF, gpio.LOW)
	gpio.setup(_UP_ARROW_PIN, gpio.OUT, gpio.PUD_OFF, gpio.LOW)
	gpio.setup(_BACK_PIN, gpio.OUT, gpio.PUD_OFF, gpio.LOW)
	gpio.setup(_DOWN_ARROW_PIN, gpio.OUT, gpio.PUD_OFF, gpio.LOW)
	gpio.setup(_UP_PIN, gpio.OUT, gpio.PUD_OFF, gpio.LOW)
	gpio.setup(_STOP_PIN, gpio.OUT, gpio.PUD_OFF, gpio.LOW)
	gpio.setup(_DOWN_PIN, gpio.OUT, gpio.PUD_OFF, gpio.LOW)
	gpio.setup(_RESET_PIN, gpio.OUT, gpio.PUD_OFF, gpio.LOW)
	gpio.setup(_POWER_ON_PIN, gpio.OUT, gpio.PUD_OFF, gpio.LOW)

def reset():
	global _ready
	_ready = False
	gpio.output(_POWER_ON_PIN, gpio.LOW)
	time.sleep(2)
	gpio.output(_RESET_PIN, gpio.HIGH)
	gpio.output(_POWER_ON_PIN, gpio.HIGH)
	time.sleep(6)
	gpio.output(_RESET_PIN, gpio.LOW)
	_ready = True

if __name__ == '__main__':
	print('Powering Velux remote, please wait until ready')
	setupGpio()
	powerOn()
	_mqttClient = mqtt.Client()
	_mqttClient.on_connect = onConnect
	_mqttClient.on_message = onMessage
	_mqttClient.connect('localhost', 1883)
	_mqttClient.loop_start()
	try:
		while _RUNNING:
			if _ready:
				button = raw_input('Type a button number: ')
				try:
					button = int(button)
				except ValueError:
					if button == 'reset':
						reset()
						continue
					else:
						print('Please use numbers from 1 to 10 only (or `reset`)')
						continue

				pin = translateButton(button)
				if pin != -1:
					gpio.output(pin, gpio.HIGH)
					time.sleep(0.25)
					gpio.output(pin, gpio.LOW)
					time.sleep(0.25)

		raise KeyboardInterrupt
	except KeyboardInterrupt:
		pass
	finally:
		if _thread is not None:
			_thread.cancel()
		gpio.cleanup()