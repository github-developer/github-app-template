#!/usr/bin/env python3

# Copyright 2019 Jetperch LLC
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

"""General purpose input and output demo with polled input mode.

This demo that drives the outputs and manually reads (polls) the inputs.
See the gpi_synchronized.py for how to read the GPI from the Joulescope
streaming data.

If you connect the OUT0 to IN0 and OUT1 to IN1, this script should print
a 2 bit counter: 0, 1, 2, 3, 0, 1, 2, 3, 0, ...
"""


from joulescope import scan_require_one
import time


def run():
    # do not use config='auto' so that we can set io_voltage first.
    with scan_require_one(name='Joulescope') as js:
        js.parameter_set('io_voltage', '3.3V')
        js.parameter_set('gpo0', '0')
        js.parameter_set('gpo1', '0')
        js.parameter_set('sensor_power', 'on')
        for count in range(17):
            js.parameter_set('gpo0', str(count & 1))
            js.parameter_set('gpo1', str((count & 2) >> 1))
            time.sleep(0.25)
            print(js.extio_status()['gpi_value']['value'])
        js.parameter_set('sensor_power', 'off')


if __name__ == '__main__':
    run()
