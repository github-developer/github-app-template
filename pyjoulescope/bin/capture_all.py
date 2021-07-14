#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

"""Capture samples to JLS files for all connected Joulescopes."""

from joulescope import scan
from joulescope.data_recorder import DataRecorder
import argparse
import os
import sys
import signal
import time


def get_parser():
    p = argparse.ArgumentParser(
        description='Read data from Joulescope.')
    p.add_argument('--duration', '-d',
                   type=lambda d: d if d is None else float(d),
                   help='The capture duration in seconds.')
    p.add_argument('--frequency', '-f',
                   help='The sampling frequency in Hz.')
    p.add_argument('--out', '-o',
                   default='out.jls',
                   help='The output path including filename.')
    return p


def run():
    quit_ = False

    def do_quit(*args, **kwargs):
        nonlocal quit_
        quit_ = 'quit from SIGINT'

    def on_stop(event, message):
        nonlocal quit_
        quit_ = 'quit from stop'

    args = get_parser().parse_args()
    filename_base, filename_ext = os.path.splitext(args.out)
    signal.signal(signal.SIGINT, do_quit)
    devices = scan(config='auto')
    items = []

    try:
        for device in devices:
            if args.frequency:
                try:
                    device.parameter_set('sampling_frequency', int(args.frequency))
                except Exception:
                    # bad frequency selected, display warning & exit gracefully
                    freqs = [f[2][0] for f in device.parameters('sampling_frequency').options]
                    print(f'Unsupported frequency selected: {args.frequency}')
                    print(f'Supported frequencies = {freqs}')
                    quit_ = True
                    break
            fname = f'{filename_base}_{device.device_serial_number}{filename_ext}'
            device.open()
            recorder = DataRecorder(fname,
                                    calibration=device.calibration)
            items.append([device, recorder])
            device.stream_process_register(recorder)

        if not quit_:
            for device, _ in items:
                device.start(stop_fn=on_stop, duration=args.duration)

        print('Capturing data: type CTRL-C to stop')
        while not quit_:
            time.sleep(0.01)
    finally:
        for device, recorder in items:
            try:
                device.stop()
                recorder.close()
                device.close()
            except Exception:
                print('exception during close')
    return 0


if __name__ == '__main__':
    run()
