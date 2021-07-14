#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2019-2020 Jetperch LLC
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

"""Print the energy consumption recorded by Joulescope using on-instrument
sensor computation."""

from joulescope import scan_require_one
from joulescope.units import three_sig_figs
import signal
import time
import queue


def run():
    statistics_queue = queue.Queue()  # resynchronize to main thread

    def stop_fn(*args, **kwargs):
        statistics_queue.put(None)  # None signals quit

    signal.signal(signal.SIGINT, stop_fn)  # also quit on CTRL-C

    with scan_require_one(config='off') as device:
        device.statistics_callback_register(statistics_queue.put, 'sensor')
        device.parameter_set('i_range', 'auto')
        device.parameter_set('v_range', '15V')
        print('CTRL-C to exit')
        while True:
            device.status()
            time.sleep(0.1)
            try:
                data = statistics_queue.get(block=False)
                if data is None:
                    break
                energy = data['accumulators']['energy']
                print(three_sig_figs(energy['value'], units=energy['units']))
            except queue.Empty:
                pass


if __name__ == '__main__':
    run()
