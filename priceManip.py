import urllib.request
import shutil
import csv
import pySON
import datetime
import time


# Dynamically retrieve .csv file from NYISO with price data
def getfile():
    today = datetime.date.today()
    today = today.strftime('%Y%m%d')
    url = 'http://mis.nyiso.com/public/csv/realtime/' + today + 'realtime_zone.csv'
    print("Obtaining data from ", url)
    with urllib.request.urlopen(url) as response, open('Todays_Data.csv', 'wb') as f:
        shutil.copyfileobj(response, f)


# Creates new file with only relevant data (regions)
# for faster reads
def refinedata(region):
    try:
        with open('Todays_Data.csv', 'r') as oldfile:
            with open('Relevant_data.csv', 'w') as newfile:
                datain = csv.reader(oldfile)
                dataout = csv.writer(newfile, lineterminator='\n')
                for row in datain:
                    if row[1] == region:
                        dataout.writerow(row)
    except FileNotFoundError:
        print("Todays_Data.csv not found")


def processdata():
    highest = 0
    lowest = 1000
    buy = False
    sell = False

    try:
        with open('Relevant_data.csv', 'r') as file:
            data = csv.reader(file)
            for row in data:
                if float(row[3]) > highest:
                    highest = float(row[3])
                if float(row[3]) < lowest:
                    lowest = float(row[3])

            highest = 0.7*highest
            lowest = 0.3*highest

            file.seek(0)
            current_price = 0
            for row in data:
                # Only process data up to the current time of day.
                # i.e. do not make decisions for times that have not happened yet
                str_time = datetime.datetime.strptime(row[0], '%m/%d/%Y %H:%M:%S').time()
                ctime = datetime.datetime.now().time()
                if ctime < str_time:
                    print(ctime, "<", str_time)
                    break

                # Get the current price for use in pricing
                current_price = float(row[3])

                # Sell if price hits 70th percentile of price
                # Buy if price hits below 30th percentile
                if current_price > highest and buy:
                    buy = False
                    sell = True
                    pySON.create_status(buy, sell, True)
                elif current_price < lowest and sell:
                    buy = True
                    sell = False
                    pySON.create_status(buy, sell, True)

            return current_price
    except FileNotFoundError:
        print("File \'Relevant_data.csv\' not found")
        return 0


def timepassed(oldtime, seconds):
    # print("Time:", time.time(), " Old Time:", oldtime)
    # print("Time - Old Time = ", time.time()-oldtime)
    return time.time() - oldtime >= seconds


def gettimepassed(start, end):
    if end > start and end != 0 and start != 0:
        return end-start
    return 0


def calcprofit(buy_time, sell_time, elcost):
    # Convert seconds to hours and MWHr to WHr
    buy_time /= 3600
    sell_time /= 3600
    elcost /= 1000000

    # Sell 306W : Buy 91WHr
    return (sell_time * 306 * elcost) - (buy_time * 91 * elcost)


if __name__ == "__main__":
    # getfile()
    # refinedata("N.Y.C.")
    # pySON.create_status(True, False)
    # processdata()
    t = time.time()
    time.sleep(5)
    print(timepassed(t, 1))
