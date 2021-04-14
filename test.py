#!/usr/bin/python3
'''test.py April 13, 2021 Larry Priest priestlt@proton.com
Recreating blinka_bridge or adafruit_ble_broadcastnet.py
Going to start from scratchish
'''
from secrets import secrets
import msmts
import requests
# from adafruit_ble import BLERadio
# import adafruit_ble_broadcastnet


def get_existing_feeds(aio_auth_header, aio_base_url, **kwargs):
    existing_feeds = {}
    kwargs['headers'] = aio_auth_header
    response = requests.get(aio_base_url+"/groups", **kwargs)
    print('return code: ', response.status_code)
    for group in response.json():
        if "-" not in group['key']:
            continue
        pieces = group['key'].split("-")
        if len(pieces) != 4 or pieces[0] != 'bridge' or pieces[2] != "sensor":
            continue
        _, bridge, _, sensor_address = pieces
        if bridge != 'b827ebdeb6d6':  # replace with bridge_address
            continue
        existing_feeds[sensor_address] = []
        for feed in group["feeds"]:
            existing_feeds[sensor_address].append(feed["key"].split(".")[-1])

        return existing_feeds


def main():
    # ble_radio = BLERadio()
    # bridge_address = adafruit_ble_broadcastnet.device_address
    aio_auth_header = {"X-AIO-KEY": secrets["aio_key"]}
    aio_base_url = "https://io.adafruit.com/api/v2/" + secrets["aio_username"]
    measurement = msmts.measure
    # print("This is BroadcastNet bridge: ", bridge_address)
    existing_feeds = get_existing_feeds(aio_auth_header, aio_base_url)
    print('existing feeds:\n', existing_feeds)


if __name__ == '__main__':
    main()
