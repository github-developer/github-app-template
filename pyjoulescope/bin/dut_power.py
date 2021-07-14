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

"""Control power to the device under test.

usage: dut_power.py [on | off]
"""


from joulescope import scan_require_one
import time
import sys


def dut_power(power_on):
    i_range = 'auto' if power_on else 'off'
    # do not use config='auto' so that power can remain off without a glitch.
    with scan_require_one(name='Joulescope') as js:
        js.parameter_set('sensor_power', 'on')
        js.parameter_set('i_range', i_range)


def run():
    power_on = True
    if len(sys.argv) > 1:
        power_on_str = sys.argv[1].lower()
        if power_on_str in ['1', 'on', 'true', 'enable']:
            power_on = True
        elif power_on_str in ['0', 'off', 'false', 'disable']:
            power_on = False
        else:
            print('usage: dut_power.py [on | off]')
            return
    dut_power(power_on)


if __name__ == '__main__':
    run()
