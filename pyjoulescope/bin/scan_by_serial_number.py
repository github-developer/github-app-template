#!/usr/bin/env python3

# Copyright 2020 Jetperch LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Scan a device by serial number.

usage: python scan_by_serial_number.py
usage: python scan_by_serial_number.py {serial_number}
"""


from joulescope import scan
import sys


def scan_by_serial_number(serial_number, name: str = None, config=None):
    devices = scan(name, config)
    for device in devices:
        if serial_number == device.device_serial_number:
            return device
    raise KeyError(f'Device not found with serial number {serial_number}')


def run(serial_number):
    with scan_by_serial_number(serial_number) as js:
        print(js.info())


def select_prompt():
    devices = scan()
    while True:
        for idx, device in enumerate(devices):
            print(f'{idx + 1}: {device.device_serial_number}')
        value = input('Type number and enter: ')
        idx = int(value)
        if 1 <= idx <= len(devices):
            device = devices[idx - 1]
            return device.device_serial_number


if __name__ == '__main__':
    if len(sys.argv) == 2:
        serial_number = sys.argv[1]
    else:
        serial_number = select_prompt()
    run(serial_number)
