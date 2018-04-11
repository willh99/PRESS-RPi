#!/usr/bin/env python

import time
import RPi.GPIO as GPIO
import signal
import json
import pySON
import priceManip

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
DEBUG = True


def signal_handler(signum, frame):
    GPIO.cleanup()


def readadc(adcnum, clockpin, mosipin, misopin, cspin):
    if (adcnum > 7) or (adcnum < 0):
        return -1
    GPIO.output(cspin, True)

    GPIO.output(clockpin, False)  # start clock low
    GPIO.output(cspin, False)  # bring CS low

    commandout = adcnum
    commandout |= 0x18  # start bit + single-ended bit
    commandout <<= 3  # we only need to send 5 bits here
    for index in range(5):
        if commandout & 0x80:
            GPIO.output(mosipin, True)
        else:
            GPIO.output(mosipin, False)
        commandout <<= 1
        GPIO.output(clockpin, True)
        GPIO.output(clockpin, False)

    adcout = 0
    # read in one empty bit, one null bit and 10 ADC bits
    for index in range(12):
        GPIO.output(clockpin, True)
        GPIO.output(clockpin, False)
        adcout <<= 1
        if GPIO.input(misopin):
            adcout |= 0x1

    GPIO.output(cspin, True)

    adcout >>= 1  # first bit is 'null' so drop it
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
GPIO.setup(ON_OFF, GPIO.IN)  # Activates Program
GPIO.setup(BC, GPIO.OUT)  # Function Battery Charger
GPIO.setup(GTI, GPIO.OUT)  # Function Grid-Tie Inverter
GPIO.output(BC, GPIO.LOW)
GPIO.output(GTI, GPIO.LOW)

# ADC Reading Points
voltage_adc = 0
temp_adc = 2
batt_temp_adc = 4

last_read = 0  # this keeps track of the last potentiometer value
tolerance = 5  # to keep from being jittery

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

# Arrays containing last 3 values of respective sensor data
# Used to filter out extraneous values
volt = [12.0]*3
temp = [23.00]*3
btemp = [25.00]*3


# Arrays to hold time spent buying  or selling
# first time is start time, second is end time, last is total runtime
buy_time = [0]*3
sell_time = [0]*3

old_status = {'Buy': True, 'Sell': True}

# Profit made by the system
profit = pySON.read_json('profit.json')
if profit == -1:
    profit = {'profit': 0, 'Sell Time': 0, 'Buy Time': 0}

while True:
    # set ADC to Voltmeter
    volt_pot = readadc(voltage_adc, SPICLK, SPIMOSI, SPIMISO, SPICS)
    volt_new = round(volt_pot * (13.14 / 1023), 2)
    if volt_new < 1.1*volt[0] and volt_new > .9*volt[0]:
        volt[0] = round((volt_new + volt[1] + volt[2])/3, 2)
    

    # Set ADC to Ambient Temperature
    temp_pot = readadc(temp_adc, SPICLK, SPIMOSI, SPIMISO, SPICS)
    temp_new = round(((temp_pot * 3300 / 1023) - 100.0) / 10 - 40, 1)
    if temp_new < 1.3*temp[0] and temp_new > .7*temp[0]:
        temp[0] = round((temp_new + temp[1] + temp[2])/3, 1)

    # Set ADC to Battery Temperature
    batt_temp_pot = readadc(batt_temp_adc, SPICLK, SPIMOSI, SPIMISO, SPICS)
    btemp_new = round(((batt_temp_pot * 3300 / 1023) - 100.0) / 10 - 40, 1)
    if btemp_new < 1.3*btemp[0] and btemp_new > .7*btemp[0]:
        btemp[0] = round((btemp_new + btemp[1] + btemp[2])/3, 1)

    # Debug to show values in terminal
    if DEBUG:
        print('voltage:', volt[0], ' V')
        print('temp:', temp[0], ' degrees C')
        print('batt temp:', btemp[0], ' degrees C\n')

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

    """
    Logic to change the state of the system (GPIO settings)
    given the values read from status.json.
    Internal if statements contain the logic to update and calculate
    the time spent buying or selling.  Start time is set to zero each
    time status is updated
    """
    if status['Sell']:
        if status['Sell'] != old_status['Sell'] or status['Buy'] != old_status['Buy']:
            sell_time[0] = buy_time[1] = time.time()
            buy_time[2] += priceManip.gettimepassed(buy_time[0], buy_time[1])
            buy_time[0] = 0
            old_status['Sell'] = status['Sell']
            old_status['Buy'] = status['Buy']
        GPIO.output(GTI, GPIO.LOW)
        GPIO.output(BC, GPIO.HIGH)
    elif status['Buy']:
        if status['Sell'] != old_status['Sell'] or status['Buy'] != old_status['Buy']:
            buy_time[0] = sell_time[1] = time.time()
            sell_time[2] += priceManip.gettimepassed(sell_time[0], sell_time[1])
            sell_time[0] = 0
            old_status['Sell'] = status['Sell']
            old_status['Buy'] = status['Buy']
        GPIO.output(BC, GPIO.LOW)
        GPIO.output(GTI, GPIO.HIGH)
    else:
        if status['Sell'] != old_status['Sell'] or status['Buy'] != old_status['Buy']:
            sell_time[1] = buy_time[1] = time.time()
            buy_time[2] += priceManip.gettimepassed(buy_time[0], buy_time[1])
            sell_time[2] += priceManip.gettimepassed(sell_time[0], sell_time[1])
            buy_time[0] = sell_time[0] = 0
            old_status['Sell'] = status['Sell']
            old_status['Buy'] = status['Buy']
        GPIO.output(GTI, GPIO.HIGH)
        GPIO.output(BC, GPIO.HIGH)

    # Add a new dictionary(json) to a list for battery voltage
    dictionary = {"Timestamp": time.asctime(time.localtime()),
                  "Voltage": volt[0]}
    if len(vlog_list) >= 5000:
        vlog_list.pop(0)
    vlog_list.append(dictionary)
    pySON.append_json(vlog_list, 'v_log.json')

    # Add a new dictionary(json) to a list for temperature
    dictionary = {"Timestamp": time.asctime(time.localtime()),
                  "temperature": temp[0]}
    if len(tlog_list) >= 5000:
        tlog_list.pop(0)
    tlog_list.append(dictionary)
    pySON.append_json(tlog_list, 't_log.json')

    # Add a new dictionary(json) to a list for inverter temperature
    dictionary = {"Timestamp": time.asctime(time.localtime()),
                  "temperature": btemp[0]}
    if len(btlog_list) >= 5000:
        btlog_list.pop(0)
    btlog_list.append(dictionary)
    pySON.append_json(btlog_list, 'bt_log.json')

    # Update the price algorithm every 3 minutes (180 seconds)
    # Also update profit based on elapsed buy/sell times since last check
    if priceManip.timepassed(oldtime, 10):
        oldtime = time.time()
        current_price = priceManip.processdata()
        profit["profit"] += priceManip.calcprofit(buy_time[2], sell_time[2], current_price)
        profit["Buy Time"] += buy_time[2]
        profit["Sell Time"] += sell_time[2]
        pySON.append_json(profit, 'profit.json')
        buy_time[2] = sell_time[2] = 0

    '''
    if push-button switch is low (toggled) set status.json to false false (off
    elif temp > 45 degrees, set status.json to false false (off)
    elif voltage < 11.5V, don't allow status.json to Sell (false false or true false)
    elif voltage > 13.1V, don't allow status.json to Sell (false false or false true)
    elif appstatus.json is not stale, set status.json to appstatus.json
    else set status.json to pricestatus.json
    '''
    if GPIO.input(ON_OFF):
        pySON.create_status(False, False, 0)
    elif temp[0] > 45.0 and temp[1] > 45.0 and temp[2] > 45.0:
        pySON.create_status(False, False, 0)
    elif volt[0] < 11.5 and volt[1] < 11.5 and volt[2] < 11.5:
        if app_status:
            if app_status["Buy"] and app_status["Sell"]:
                if price_status["Buy"]:
                    pySON.create_status(True, False, 0)
                else:
                    pySON.create_status(False, False, 0)
            elif app_status["Buy"]:
                pySON.create_status(True, False, 0)
            else:
                pySON.create_status(False, False, 0)
        elif price_status["Buy"]:
            pySON.create_status(True, False, 0)
        else:
            pySON.create_status(False, False, 0)
    elif volt[0] >= 13.1 and volt[1] >= 13.1 and volt[2] >= 13.1:
        if app_status:
            if app_status["Buy"] and app_status["Sell"]:
                if price_status["Sell"]:
                    pySON.create_status(False, True, 0)
                else:
                    pySON.create_status(False, False, 0)
            elif app_status["Sell"]:
                pySON.create_status(False, True, 0)
            else:
                pySON.create_status(False, False, 0)
        elif price_status["Sell"]:
            pySON.create_status(False, True, 0)
        else:
            pySON.create_status(False, False, 0)
    elif app_status:
        if app_status["Buy"] and app_status["Sell"]:
            pySON.create_status(price_status["Buy"], price_status["Sell"], 0)
        else:
            pySON.create_status(app_status["Buy"], app_status["Sell"], 0)
    else:
        pySON.create_status(price_status["Buy"], price_status["Sell"], 0)

    # Rotate values in voltage array, disposing of oldest value
    for i in range(2, 0, -1):
        volt[i] = volt[i - 1]
        temp[i] = temp[i - 1]
        btemp[i] = btemp[i - 1]

    time.sleep(1)
