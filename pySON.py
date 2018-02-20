import json
import time
import random
import datetime


def read_json(filename):
    if '.json' not in filename:
        return -1
    try:
        with open(filename, 'r') as f:
            print("File \"", filename, "\" found", sep='')
            data = json.load(f)
            return data
    except FileNotFoundError:
        print("File Not Found")
        return -1


def append_json(data):
    with open('v_log.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        print("wrote to file")


def create_status(buy, sell):
    now = datetime.datetime.now()
    now = now.strftime('%d-%m-%Y %X')
    data = {"Sell": sell, "Buy": buy, "Timestamp": now}
    with open('status.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    json_list = []
    for x in range(0, 100):
        i = random.random()*12.8
        dictionary = {"Timestamp": time.asctime(time.localtime()),
                      "Voltage": round(i, 6)}

        if len(json_list) >= 50:
            json_list.pop(0)
        json_list.append(dictionary)
        # time.sleep(.2)

    append_json(json_list)

    something = read_json('status.json')
    if something is not -1:
        print(json.dumps(something, indent=2))

