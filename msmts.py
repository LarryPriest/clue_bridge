#!/usr/bin/python3
'''
msmts.py - dictionary of Adafruit mesurements
Dec 11/2020
Larry T. Priest - larrytpriest@gmail.com
used for receiving data from centrals on BLE
'''

measure = {
            '040a': ("temperature", "f"),
            '010a': ("magnetic", "fff"),
            '0300': ("sequence-number", "B"),
            '0a0a': ("pressure", "f"),
            '0b0a': ("relative-humidity", "f"),
            '000a': ("acceleration", "fff")
          }
