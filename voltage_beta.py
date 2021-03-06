#!/usr/bin/env python

import time
from datetime import datetime
import os
import RPi.GPIO as GPIO
import signal
import json
import pySON
import priceManip

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
DEBUG = 1


def signal_handler(signum, frame):
        GPIO.cleanup()

        
# read SPI data from MCP3008 chip, 8 possible adc's (0 thru 7)
def readadc(adcnum, clockpin, mosipin, misopin, cspin):
        if ((adcnum > 7) or (adcnum < 0)):
                return -1
        GPIO.output(cspin, True)

        GPIO.output(clockpin, False)  # start clock low
        GPIO.output(cspin, False)     # bring CS low

        commandout = adcnum
        commandout |= 0x18  # start bit + single-ended bit
        commandout <<= 3    # we only need to send 5 bits here
        for i in range(5):
                if (commandout & 0x80):
                        GPIO.output(mosipin, True)
                else:
                        GPIO.output(mosipin, False)
                commandout <<= 1
                GPIO.output(clockpin, True)
                GPIO.output(clockpin, False)

        adcout = 0
        # read in one empty bit, one null bit and 10 ADC bits
        for i in range(12):
                GPIO.output(clockpin, True)
                GPIO.output(clockpin, False)
                adcout <<= 1
                if (GPIO.input(misopin)):
                        adcout |= 0x1

        GPIO.output(cspin, True)
        
        adcout >>= 1       # first bit is 'null' so drop it
        return adcout

# Pins Connected from the ADC (MCP3008) to the Raspberry Pi
SPICLK = 18
SPIMISO = 23
SPIMOSI = 24
SPICS = 25
GTI = 26
BC = 21
ON_OFF = 6

# set up the SPI interface pins
GPIO.setup(SPIMOSI, GPIO.OUT)
GPIO.setup(SPIMISO, GPIO.IN)
GPIO.setup(SPICLK, GPIO.OUT)
GPIO.setup(SPICS, GPIO.OUT)
GPIO.setup(ON_OFF,GPIO.IN)         # Activates Program
GPIO.setup(BC,GPIO.OUT)       # Function Battery Charger
GPIO.setup(GTI,GPIO.OUT)      # Function Grid-Tie Inverter
GPIO.output(BC,GPIO.LOW)
GPIO.output(GTI,GPIO.LOW)


#ADC Reading Points
voltage_adc = 0
temp_adc = 2
batt_temp_adc = 4

last_read = 0       # this keeps track of the last potentiometer value
tolerance = 5       # to keep from being jittery
                
original_sigint = signal.getsignal(signal.SIGINT)
signal.signal(signal.SIGINT, signal_handler)

# Get .csv file from the Internet
priceManip.getfile()
priceManip.refinedata('N.Y.C.')
priceManip.processdata()
oldtime = time.time()

# JSON Lists for voltage and temperature
vlog_list = pySON.read_json('v_log.json')
tlog_list = pySON.read_json('t_log.json')
btlog_list = pySON.read_json('bt_log.json')
if vlog_list == -1:
        vlog_list = []
if tlog_list == -1:
        tlog_list = []
if btlog_list == -1:
        btlog_list = []

volt = [0]*3
temp = [0]*3
btemp = [0]*3

while True:
        GPIO.output(GTI,GPIO.HIGH)
        GPIO.output(BC,GPIO.HIGH)

        while GPIO.input(ON_OFF):

                
                # set ADC to Voltmeter
                #GPIO.output(19,GPIO.HIGH)
                #time.sleep(.2)
                volt_pot = readadc(voltage_adc, SPICLK, SPIMOSI, SPIMISO, SPICS)
                volt[0] = round(volt_pot*(13.14/1023),2)
                #print('voltage pot:', volt_pot)
                print('voltage:', volt[0],' V')

                # Set ADC to Ambient Temperature
                temp_pot = readadc(temp_adc, SPICLK, SPIMOSI, SPIMISO, SPICS)
                temp[0] = round(((temp_pot * 3300 / 1023)-100.0)/10 - 40,1)
                #print('temp pot:', temp_pot)
                print('temp:', temp[0], ' degrees C')

                # Set ADC to Battery Temperature
                batt_temp_pot = readadc(batt_temp_adc, SPICLK, SPIMOSI, SPIMISO, SPICS)
                btemp[0] = round(((batt_temp_pot * 3300 / 1023)-100.0)/10 - 40,1)
                #print('batt temp pot:', batt_temp_pot)
                print('batt temp:', btemp[0],' degrees C\n')

                with open('status.json', 'r') as f:
                        status = json.load(f)
                with open('price_status.json', 'r') as f:
                        price_status = json.load(f)
                try:
                        with open('appstatus.json', 'r') as f:
                                app_status = json.load(f)
                except FileNotFoundError:
                        print("ERROR: File \'appstatus.json\' not found")
                        app_status = None
                        
                #print(status)
                if status['Sell'] == True:
                        GPIO.output(GTI,GPIO.LOW)
                        GPIO.output(BC,GPIO.HIGH)
                elif status['Buy'] == True:
                        GPIO.output(BC,GPIO.LOW)
                        GPIO.output(GTI,GPIO.HIGH)
                else:
                       GPIO.output(GTI,GPIO.HIGH)
                       GPIO.output(BC,GPIO.HIGH)

                # Add a new dictionary(json) to a list for voltage
                dictionary = {"Timestamp": time.asctime(time.localtime()),
                          "Voltage": volt[0]}
                if len(vlog_list) >= 1000:
                        vlog_list.pop(0)
                vlog_list.append(dictionary)
                pySON.append_json(vlog_list, 'v_log.json')

                # Add a new dictionary(json) to a list for temperature
                dictionary = {"Timestamp": time.asctime(time.localtime()),
                          "temperature": temp[0]}
                if len(tlog_list) >= 1000:
                        tlog_list.pop(0)
                tlog_list.append(dictionary)
                pySON.append_json(tlog_list, 't_log.json')

                # Add a new dictionary(json) to a list for inverter temperature
                dictionary = {"Timestamp": time.asctime(time.localtime()),
                          "batt_temperature": btemp[0]}
                if len(btlog_list) >= 1000:
                        btlog_list.pop(0)
                btlog_list.append(dictionary)
                pySON.append_json(btlog_list, 'bt_log.json')

                # Update the price algorithm every 3 minutes (180 seconds)
                if(priceManip.timepassed(oldtime, 180)):
                        oldtime = time.time()
                        priceManip.processdata()
                        
                # TODO:
                '''
                if temp > 45 degrees, set status.json to false false (off)
                elif voltage < 11.5V, don't allow status.json to Sell (false false or true false)
                elif voltage > 13.1V, don't allow status.json to Sell (false false or false true)
                elif appstatus.json is not stale, set status.json to appstatus.json
                else set status.json to pricestatus.json
                '''
                if temp[0] > 45.0 and temp[1] > 45.0 and temp[2] > 45.0:
                        pySON.create_status(False,False,0)
                elif volt[0] < 11.5 and volt[1] < 11.5 and volt[2] < 11.5:
                        if app_status:
                                if app_status["Buy"] and app_status["Sell"]:
                                        if price_status["Buy"] == True:
                                                pySON.create_status(True,False,0)
                                        else:
                                                pySON.create_status(False,False,0)
                                elif app_status["Buy"]:
                                        pySON.create_status(True,False,0)
                                else:
                                        pySON.create_status(False,False,0)
                        elif price_status["Buy"]:
                                pySON.create_status(True,False,0)
                        else:
                                pySON.create_status(False,False,0)
                elif volt[0] >= 13.1 and volt[1] >= 13.1 and volt[2] >= 13.1:
                        if app_status:
                                if app_status["Buy"] and app_status["Sell"]:
                                        if price_status["Sell"] == True:
                                                pySON.create_status(False,True,0)
                                        else:
                                                pySON.create_status(False,False,0)
                                elif app_status["Sell"]:
                                        pySON.create_status(False,True,0)
                                else:
                                        pySON.create_status(False,False,0)
                        elif price_status["Sell"]:
                                pySON.create_status(False,True,0)
                        else:
                                pySON.create_status(False,False,0)
                elif app_status:
                        if app_status["Buy"] and app_status["Sell"]:
                                pySON.create_status(price_status["Buy"],price_status["Sell"],0)
                        else:
                                pySON.create_status(app_status["Buy"],app_status["Sell"],0)
                else:
                        pySON.create_status(price_status["Buy"],price_status["Sell"],0)


                for i in range(2,0,-1):
                        volt[i]=volt[i-1]
                        temp[i]=temp[i-1]
                        btemp[i]=btemp[i-1]

                time.sleep(.5)



