#!/usr/bin/python3
'''This example scans for any BLE advertisements and prints one advertisement and
one scan response from every device found. This scan is more detailed than the
simple test because it includes specialty advertising types.  from:
https://circuitpython.readthedocs.io/projects/ble/en/latest/examples.html#detailed-scan
started on nov 23/2020 - LTP
'''
from adafruit_ble import BLERadio
import sys
import time
from secrets import secrets
import requests
import adafruit_ble_broadcastnet
import struct
from measurementCode import measurement  # contains dict of codes & data types.

macaddr = secrets["macaddr"]  # MAC Address for each sensor pack

ble = BLERadio()
bridge_address = adafruit_ble_broadcastnet.device_address
print("This is BroadcastNet bridge:", bridge_address)

# io. adafruit creds.
aio_auth_header = {"X-AIO-KEY": secrets["aio_key"]}
aio_base_url = "https://io.adafruit.com/api/v2/" + secrets["aio_username"]


def aio_post(path, **kwargs):
    '''Post the data collected'''
    kwargs["headers"] = aio_auth_header
    print("posting stuff")
    temp_response = False
    try:
        temp_response = requests.post(aio_base_url + path, **kwargs)
    except requests.exceptions.ConnectionError:
        print('No joy in post ville')
    return temp_response


def aio_get(path, **kwargs):
    '''Get the existing data feeds'''
    kwargs["headers"] = aio_auth_header
    # ~ print("getting stuff")
    return requests.get(aio_base_url + path, **kwargs)


def create_group(name):
    '''Create a groub if the sensor package is not found'''
    response = aio_post("/groups", json={"name": name})
    if response.status_code != 201:
        print(name)
        print(response.content)
        print(response.status_code)
        raise RuntimeError("unable to create new group")
    return response.json()["key"]


def create_feed(group_key, name):
    '''Create a new data feed if one does not exist for our sensor'''
    # ~ print("creating feed\n", name)
    response = aio_post(
        "/groups/{}/feeds".format(group_key), json={"feed": {"name": name}})
    if response.status_code != 201:
        print(name)
        print(response.content)
        print(response.status_code)
        raise RuntimeError("unable to create new feed")
    return response.json()["key"]


def create_data(group_key, data):
    '''Create the data blob to be sent to io.adafruit.com. '''
    print("groups {}/ndata/n{}".format(group_key, data))
    response = aio_post("/groups/{}/data".format(group_key), json={"feeds": data})
    if response.status_code == 429:
        print("Throttled!")
        return False
    if response.status_code != 200:
        print(response.status_code, response.json())
        raise RuntimeError("unable to create new data")
    response.close()
    return True


def convert_to_feed_data(values, attribute_name, attribute_instance):
    '''Convert the Python data to io.adafruit format '''
    feed_data = []
    # Wrap single value entries for enumeration.
    if not isinstance(values, tuple) or (
            attribute_instance.element_count > 1 and not isinstance(values[0], tuple)):
        values = (values,)
    for i, value in enumerate(values):
        key = attribute_name.replace("_", "-") + "-" + str(i)
        if isinstance(value, tuple):
            for j in range(attribute_instance.element_count):
                feed_data.append({"key": key + "-" + attribute_instance.field_names[j],
                                  "value": value[j], })
        else:
            feed_data.append({"key": key, "value": value})
    return feed_data


def retrieve_existing_feeds():
    """Retrieve existing feeds from io.adafruit. """

    print("Fetching existing feeds.")
    existing_feeds = {}
    response = aio_get("/groups")
    print("response\n", response)
    for group in response.json():
        if "-" not in group["key"]:
            continue
        pieces = group["key"].split("-")
        if len(pieces) != 4 or pieces[0] != "bridge" or pieces[2] != "sensor":
            continue
        _, bridge, _, sensor_address = pieces
        if bridge != bridge_address:
            continue
        existing_feeds[sensor_address] = []
        for feed in group["feeds"]:
            feed_key = feed["key"].split(".")[-1]
            existing_feeds[sensor_address].append(feed_key)

    print("existing feeds:\n", existing_feeds)
    return existing_feeds


def collect_data(data_bytes):
    '''Convert the byte stream data to a dict. '''
    feed_data = []
    start = 2
    measurementBytes: bytes = data_bytes[start:len(data_bytes)]
    length = len(measurementBytes)
    while length > 3:
        bytecode = measurementBytes[1], measurementBytes[2]
        code = bytes(bytecode).hex()
        if code in measurement:
            if measurement[code][1] == 'B':
                value = struct.unpack_from(measurement[code][
                    1], measurementBytes, offset=3)
                value = value[0]
                measurementBytes = measurementBytes[3+(len(measurement[code][1])):]
                length = len(measurementBytes)
            elif measurement[code][1] == 'f':
                value = struct.unpack_from(measurement[code][
                    1], measurementBytes, offset=3)
                measurementBytes = measurementBytes[3+(len(measurement[code][1])*4):]
                length = len(measurementBytes)
                feed_data.append({"key": measurement[code][0], "value": value[0]})
            else:
                coordinate = ('x', 'y', 'z')
                value = struct.unpack_from(measurement[code][
                    1], measurementBytes, offset=3)
                for i in range(len(measurement[code][1])):
                    feed_data.append({"key": measurement[code][0]+'-'+coordinate[i],
                                      "value": value[i]})
                measurementBytes = measurementBytes[3+(len(measurement[code][1])*4):]
                length = len(measurementBytes)
        else:
            print('unknown measurement code')

    print('finished collectiong data')
    return feed_data


def main():
    existing_feeds = retrieve_existing_feeds()

    sequence_numbers = {}
    for addr in macaddr:
        sequence_numbers[addr] = 0
    print("scanning for sensors")
    while True:

        try:
            number_missed = 0
            for advertisement in ble.start_scan():  # this one sort of works
                sensor_address = advertisement.address.string.replace(":", "")
                if sensor_address in macaddr:
                    try:   # except KeyError used to break out of try loop
                        group_key = "bridge-{}-sensor-{}".format(
                            bridge_address, sensor_address)
                        if sensor_address not in existing_feeds:
                            print("sensor not in existing feeds", sensor_address)
                            create_group("Bridge {} Sensor {}".format(
                                bridge_address, sensor_address))
                            create_feed(group_key, "Missed Message Count")
                            existing_feeds[sensor_address] = ["missed-message-count"]
                            sequence_numbers[sensor_address] = 0
                        # checking for sequence number current the first data item
                        bytecode = advertisement.data_dict[255][3], advertisement.data_dict[255][4]
                        code = bytes(bytecode).hex()
                        if code not in measurement:
                            print('no valid measurement code')
                            raise KeyError

                        sequence_number = struct.unpack_from(
                            'B', advertisement.data_dict[255], offset=5)
                        sequence_number = sequence_number[0]

                        if sequence_number == sequence_numbers[sensor_address]:
                            print('done this one', sequence_number)
                            raise KeyError  # already processed done this one
                        elif sequence_number == (sequence_numbers[sensor_address] + 1):
                            sequence_numbers[sensor_address] = sequence_number

                        else:
                            number_missed = (sequence_number -
                                             sequence_numbers[sensor_address])
                            print('We have missed: ', number_missed, 'packets')
                            print('old seq. number:', sequence_numbers[sensor_address],
                                  'new seq. # :', sequence_number)

                        print('done our checks')
                        data = [{"key": "missed-message-count", "value": number_missed}]
                        data.extend(collect_data(advertisement.data_dict[255]))

                        start_time = time.monotonic()
                        print(group_key, data)
                        if create_data(group_key, data):
                            sequence_numbers[sensor_address] = sequence_number
                        duration = time.monotonic() - start_time
                        print("Done logging msmts. to IO. Took {:.6f} seconds"
                              .format(duration))

                    except KeyError:
                        continue

                    print()
        except KeyboardInterrupt:
            print(' \n \n')
            break


if __name__ == '__main__':
    main()
print("scan done")
ble.stop_scan()
print('End It')
sys.exit()
