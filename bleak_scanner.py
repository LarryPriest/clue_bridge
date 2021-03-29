#!/usr/bin/python3
# from https://bleak.readthedocs.io/en/latest/scanning.html
# nov 23/2020 - LTP
import asyncio
from bleak import BleakScanner

async def run():
    devices = await BleakScanner.discover()
    for d in devices:
        print(d)
    
loop = asyncio.get_event_loop()
loop.run_until_complete(run())
