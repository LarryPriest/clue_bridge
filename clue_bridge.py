#!/usr/bin/python3
# This example scans for any BLE advertisements and prints one advertisement and one scan response
# from every device found. This scan is more detailed than the simple test because it includes
# specialty advertising types.
# from: https://circuitpython.readthedocs.io/projects/ble/en/latest/examples.html#detailed-scan
# nov 23/2020 - LTP

from adafruit_ble import BLERadio
import sys
import time
from secrets import secrets
import requests
#from adafruit_ble.advertising import Advertisement
# ~ from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
# ~ from adafruit_ble.advertising import Advertisement, LazyObjectField
# ~ from adafruit_ble.advertising.standard import ManufacturerData, ManufacturerDataField
import adafruit_ble_broadcastnet
import adafruit_ble
# ~ from adafruit_ble_broadcastnet import AdafruitSensorMeasurement
# ~ from adafruit_ble import advertising
import struct
import msmts  # msmts contains a dict of mesurement codes and data format

trans_meas = msmts.measure # get the codes
macaddr = secrets["macaddr"]
print("mac address", macaddr)
    
ble = BLERadio()
bridge_address = adafruit_ble_broadcastnet.device_address
print("This is BroadcastNet bridge:", bridge_address)

aio_auth_header = {"X-AIO-KEY": secrets["aio_key"]}
aio_base_url = "https://io.adafruit.com/api/v2/" + secrets["aio_username"]


def aio_post(path, **kwargs):
    kwargs["headers"] = aio_auth_header
    # ~ print("posting stuff")
    return requests.post(aio_base_url + path, **kwargs)


def aio_get(path, **kwargs):
    kwargs["headers"] = aio_auth_header
    # ~ print("getting stuff")
    return requests.get(aio_base_url + path, **kwargs)
    
def create_group(name):
    response = aio_post("/groups", json={"name": name})
    if response.status_code != 201:
        print(name)
        print(response.content)
        print(response.status_code)
        raise RuntimeError("unable to create new group")
    return response.json()["key"]


def create_feed(group_key, name):
    # ~ print("creating feed\n", name)
    response = aio_post(
        "/groups/{}/feeds".format(group_key), json={"feed": {"name": name}}
    )
    if response.status_code != 201:
        print(name)
        print(response.content)
        print(response.status_code)
        raise RuntimeError("unable to create new feed")
    return response.json()["key"]


def create_data(group_key, data):
    print("getting ready to post:", group_key)
    for i in data:
        print( '{} : {:.2f}'.format(i['key'], i['value']))
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
    feed_data = []
    # Wrap single value entries for enumeration.
    if not isinstance(values, tuple) or (
        attribute_instance.element_count > 1 and not isinstance(values[0], tuple)
    ):
        values = (values,)
    for i, value in enumerate(values):
        key = attribute_name.replace("_", "-") + "-" + str(i)
        if isinstance(value, tuple):
            for j in range(attribute_instance.element_count):
                feed_data.append(
                    {
                        "key": key + "-" + attribute_instance.field_names[j],
                        "value": value[j],
                    }
                )
        else:
            feed_data.append({"key": key, "value": value})
    return feed_data


print()
print("scanning")
found = set()
scan_responses = set()
print("Fetching existing feeds.")

existing_feeds = {}
response = aio_get("/groups")
print("response\n",response)
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
    # ~ print("groups", group["feeds"])
    for feed in group["feeds"]:
        feed_key = feed["key"].split(".")[-1]
        existing_feeds[sensor_address].append(feed_key)

print("existing feeds:\n",existing_feeds)
sequence_numbers = {}
print("scanning...")
while True:
    
    try:
        for advertisement in ble.start_scan(): # this one sort of works
            sensor_address = advertisement.address.string.replace(":","")
            if sensor_address in macaddr:
                print("found: ", sensor_address)
               
                if advertisement.scan_response and sensor_address not in scan_responses:
                    scan_responses.add(sensor_address)
                elif not advertisement.scan_response and sensor_address not in found:
                    found.add(sensor_address)
                else:
                    pass
               

            # prepare for data extraction
                feed_data = []
                try:   # try this except if we get a KeyError i.e. if the data_dict[255] not exixt
                    start = 1 # because 0 (the first byte of the data_dict is wrong
                    dd = advertisement.data_dict[255] # key[255] is data fleld 
                    sm: bytes = dd[start:len(dd)]  # extract as bytes the start to end of dd
                    
                    while len(sm) > 3: # the last entery of dd will be a sequence number(2bytes for code one for value
                        start_index = sm[1] # total bytes
                        fd = sm[2],sm[3]  # first measurment code
                        tt = bytes(fd).hex()  # convert bytes to hex
                        try:
                            mt = trans_meas[tt][0] # check to see if valid code
                        except KeyError:
                            print("measurement not found")
                        
                        else: # found a code so get the data format & extract the data correctly
                            # ~ c = trans_meas[tt][1]
                            val = struct.unpack(trans_meas[tt][1], bytes(sm[4:(sm[1]+2)]))
                            if len(val) == 1:
                                if trans_meas[tt][1] =='B':  # checking for byte seq # **need to fix the sqn and missednum stuff.
                                    sn = int(val[0])
                                    print('Seq.#: ', sn)
                                else:
                                    val = val[0]
                                    feed_data.append({"key":mt, "value":val})
                            else:
                                var = ("x", "y", "z")
                                for x in range(len(val)):
                                    feed_data.append({"key":mt+'-'+var[x], 'value':val[x]})

                        sm = sm[(start + sm[1]):len(sm)] # drop the processed data from list
                        
                except KeyError: 
                    pass
                data = feed_data
                if sensor_address not in sequence_numbers:
                    # ~ sequence_numbers[sensor_address] = sn
                    number_missed = 0
                else:
                    if not (sn == (sequence_numbers[sensor_address] + 1)) :
                        number_missed = sn - sequence_numbers[sensor_address]
                        print( 'We have missed: ', number_missed, 'packets')
                        print('old seq. number:', sequence_numbers[sensor_address],
                                'new seq. # :', sn)
                        # ~ sequence_numbers[sensor_address] = sn
                        number_missed = 0
                start_time = time.monotonic()
                group_key = "bridge-{}-sensor-{}".format(bridge_address, sensor_address)
                if sensor_address not in existing_feeds:
                    print("sensor not in existing feeds")
                    create_group("Bridge {} Sensor {}".format(bridge_address, sensor_address))
                    create_feed(group_key, "Missed Message Count")
                    existing_feeds[sensor_address] = ["missed-message-count"]
                # ~ print("exissting feeds", existing_feeds)   
                for feed_data in data:
                    if feed_data["key"] not in existing_feeds[sensor_address]:
                        print("creating feed", feed_data['key'])
                        create_feed(group_key, feed_data["key"])
                        existing_feeds[sensor_address].append(feed_data["key"])
                
        # Only update the previous sequence if we logged successfully.
               
                # if create_data(group_key, data):
                    # sequence_numbers[sensor_address] = sn
                duration = time.monotonic() - start_time
                print("Done logging measurement to IO. Took {:.6f} seconds".format(duration))
                print()
    except KeyboardInterrupt:
        print(' \n \n')
        break

print("scan done")
ble.stop_scan()
print("found:\n", found)
print()
print("responses:\n", scan_responses)
print("sequence_numbers:\n", sequence_numbers)
# sys.exit()
