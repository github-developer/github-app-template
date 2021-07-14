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

"""Disconnect the target output when the input voltage drops below a threshold."""

from joulescope import scan_require_one
import argparse
import signal
import time
import datetime


def get_parser():
    p = argparse.ArgumentParser(
        description='Disconnect the target output when the input voltage drops below a threshold.')
    p.add_argument('--threshold', '-t',
                   default=3.0,
                   type=float,
                   help='The minimum voltage threshold.')
    return p


def run():
    _quit = False
    args = get_parser().parse_args()

    def on_stop(*args, **kwargs):
        nonlocal _quit
        _quit = True

    def on_statistics(statistics):
        nonlocal _quit
        v_data = statistics['signals']['voltage']['µ']
        v = v_data['value']
        u = v_data['units']
        now = str(datetime.datetime.now())
        print(f'{now} : {v:.3f} {u}')
        if v < args.threshold:
            print(f'{now} : input voltage below threshold')
            _quit = True

    device = scan_require_one(config='auto')
    device.parameter_set('buffer_duration', 2)  # could be smaller
    signal.signal(signal.SIGINT, on_stop)

    # Perform the data capture
    with device:
        device.statistics_callback = on_statistics
        device.start(stop_fn=on_stop)
        while not _quit:
            time.sleep(0.1)
        device.stop()  # for CTRL-C handling (safe for duplicate calls)
    return 0


if __name__ == '__main__':
    run()
