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

"""Display statistics from all connected Joulescopes."""

from joulescope import scan
import signal
import time
import queue


def statistics_callback(serial_number, stats):
    """The function called for each statistics.

    :param serial_number: The serial number producing with this update.
    :param stats: The statistics data structure.
    """
    t = stats['time']['range']['value'][0]
    i = stats['signals']['current']['µ']
    v = stats['signals']['voltage']['µ']
    p = stats['signals']['power']['µ']
    c = stats['accumulators']['charge']
    e = stats['accumulators']['energy']

    fmts = ['{x:.9f}', '{x:.3f}', '{x:.9f}', '{x:.9f}', '{x:.9f}']
    values = []
    for k, fmt in zip([i, v, p, c, e], fmts):
        value = fmt.format(x=k['value'])
        value = f'{value} {k["units"]}'
        values.append(value)
    ', '.join(values)
    print(f"{serial_number} {t:.1f}: " + ', '.join(values))


def statistics_callback_factory(device, queue):
    def cbk(data, indicator=None):
        serial_number = str(device).split(':')[-1]
        queue.put((serial_number, data))
    return cbk


def handle_queue(q):
    while True:
        try:
            args = q.get(block=False)
            statistics_callback(*args)
        except queue.Empty:
            return  # no more data


def run():
    _quit = False
    statistics_queue = queue.Queue()  # resynchronize to main thread

    def stop_fn(*args, **kwargs):
        nonlocal _quit
        _quit = True

    signal.signal(signal.SIGINT, stop_fn)  # also quit on CTRL-C
    devices = scan(config='off')
    try:
        for device in devices:
            cbk = statistics_callback_factory(device, statistics_queue)
            device.statistics_callback_register(cbk, 'sensor')
            device.open()
            device.parameter_set('i_range', 'auto')
            device.parameter_set('v_range', '15V')
        while not _quit:
            for device in devices:
                device.status()
            time.sleep(0.1)
            handle_queue(statistics_queue)

    finally:
        for device in devices:
            device.close()


if __name__ == '__main__':
    run()
