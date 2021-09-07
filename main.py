from time import sleep, time
import RPi.GPIO as GPIO
from encoder import Encoder
import RPi_I2C_driver
from subprocess import run
from os import system
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import discord_notify as dn
import re
import traceback

shortPressTime = 300
longPressTime = 1500
volumeKnobMultiplier = 1
minVolume = 1
maxVolume = 20

client_id = "739f04390893451786bd1bae9e687afb"  # spotify client id
client_secret = "f133cb4d0eb7404da5e896bbc12c680d"  # spotify client secret
playlist_id = "spotify:playlist:6oTPP7TBD2d0PCDVvJvlOe"


def volumeChange(value):
	volume = min(max(value * volumeKnobMultiplier, minVolume), maxVolume)
	system(f"mpc volume {int(volume)}")
	volumeKnob.value = volume / volumeKnobMultiplier


def shortButtonPress():
	GPIO.output(16, GPIO.HIGH)
	display.backlight(True)
	system("mpc clear")
	system("mpc volume 1")
	volumeKnob.value = 1
	system("mpc random on")
	system("mpc add " + playlist_id)
	system("mpc play")
	title, artist, added_by = getCurrentlyPlaying()
	display.lcd_clear()
	display.lcd_display_string_pos(title, 1, 0)
	display.lcd_display_string_pos(added_by, 2, 0)
	discord.send(f"sev is currently listening to `{title}` by `{artist}`\nFuck you **{added_by}**!")


def longButtonPress():
	GPIO.output(16, GPIO.LOW)
	system("mpc clear")
	display.backlight(False)
	display.lcd_clear()


GPIO.setmode(GPIO.BCM)
GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(16, GPIO.OUT)
volumeKnob = Encoder(24, 25, volumeChange)
display = RPi_I2C_driver.lcd()
display.backlight(False)
client_credentials_manager = SpotifyClientCredentials(client_id, client_secret)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
discord = dn.Notifier(
	"https://discord.com/api/webhooks/871463512285794374/4J3kNNjFACMt_zkylMforzZKXdSQJRW2q7AT1LhVLeHveTT6PGJckTxNrA_CQIDsWFkr")


def getCurrentlyPlaying():
	timestamp = time() * 1000
	try:
		while True:  # wait for song to play
			output = run(["mpc", "current"], capture_output=True, text=True).stdout[:-1]
			if output != '':
				print(output)
				artist, raw_title = output.split(' - ', 1)
				title = re.sub('\(.*?\)', '', raw_title)
				title = re.sub('[^A-Za-z0-9; ]+', '', title)
				artist = re.sub('[^A-Za-z0-9; ]+', '', artist)

				title = title.split(' feat ')[0].strip()
				artist = artist.split(';')[0].strip()

				print(title + ' - ' + artist)

				added_by = getUsernameFromSong(raw_title)
				print(added_by)
				return title, artist, added_by
			else:
				sleep(.01)
			
			if time() * 1000 > timestamp + 500: # timeout after 500ms
				raise Exception("Timed out")
	except Exception:
		print(traceback.format_exc())
		return "something", "went", "wrong"

def getUsernameFromSong(song_name):
	playlist = sp.playlist_items(
		playlist_id, fields="items(added_by.id, track.name)")["items"]
	for song in playlist:
		if song["track"]["name"] == song_name:
			user = sp.user(song["added_by"]["id"])["display_name"]
			return user
	return "shit, i messed up"

while True:
	try:
		prev_state = GPIO.input(23)
		pressedTime = 0
		releasedTime = 0
		isPressing = False
		isLongDetected = False

		while True:
			state = GPIO.input(23)

			if prev_state == 1 and state == 0:  # if button is pressed
				pressedTime = int(time() * 1000)
				isPressing = True
				isLongDetected = False

			if prev_state == 0 and state == 1:  # if button is released
				isPressing = False
				releasedTime = int(time() * 1000)

				pressDuration = releasedTime - pressedTime

				if pressDuration < shortPressTime:
					shortButtonPress()

			if isPressing == True and isLongDetected == False:
				pressDuration = int(time() * 1000) - pressedTime

				if pressDuration > longPressTime:
					isLongDetected = True
					longButtonPress()

			prev_state = state
			sleep(.01)
	except Exception:
		print(traceback.format_exc())


GPIO.output(16, GPIO.LOW)
display.cleanup()
system("mpc clear")
