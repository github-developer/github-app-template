#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

"""Print the energy consumption recorded by Joulescope using host-side computation."""

from joulescope import scan_require_one
from joulescope.units import three_sig_figs
import signal
import queue


def run():
    statistics_queue = queue.Queue()  # resynchronize to main thread

    def stop_fn(*args, **kwargs):
        statistics_queue.put(None)  # None signals quit

    signal.signal(signal.SIGINT, stop_fn)  # also quit on CTRL-C

    with scan_require_one(config='auto') as device:
        device.statistics_callback = statistics_queue.put  # put data in queue
        device.start(stop_fn=stop_fn)
        print('CTRL-C to exit')
        while True:
            data = statistics_queue.get()
            if data is None:
                break
            energy = data['accumulators']['energy']
            print(three_sig_figs(energy['value'], units=energy['units']))


if __name__ == '__main__':
    run()
