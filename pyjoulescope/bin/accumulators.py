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

"""Capture and display energy and charge.

This example is a slightly more complicated version of energy_printer.
It prints both charge and energy and a configurable interval.
The program can also stop automatically after an option duration.
"""

from joulescope import scan_require_one
from joulescope.units import three_sig_figs
import argparse
import logging
import numpy as np
import signal
import time


def int_or_none(x):
    if x is None:
        return x
    return int(x)


def get_parser():
    p = argparse.ArgumentParser(
        description='Capture and display energy and charge.')
    p.add_argument('--duration', '-d',
                   type=int_or_none,
                   help='The capture duration in seconds.')
    p.add_argument('--update', '-u',
                   default=60,
                   type=int_or_none,
                   help='The interval to periodically print the accumulated value in seconds.')
    p.add_argument('--source', '-s',
                   default='stream_buffer',
                   choices=['stream_buffer', 'sensor'],
                   help='Select the source for the accumulator data.')
    return p


class Accumulators:

    def __init__(self):
        self._quit = False
        self._statistics = None
        self._update_previous = 0.0
        self._update_interval = 60.0

    def _on_user_exit(self, *args, **kwargs):
        if not self._quit:
            print('\nUser exit requested.')
        self._quit = True
        
    def _on_stop(self, *args, **kwargs):
        if not self._quit:
            print('\nCapture duration completed.')
        self._quit = True

    def _on_statistics(self, statistics):
        self._statistics = statistics
        duration_now = self._statistics['time']['range']['value'][0]
        if duration_now >= self._update_previous + self._update_interval:
            print(self._statistics_to_user_str())
            self._update_previous += self._update_interval

    def _statistics_to_user_str(self):
        if self._statistics is None:
            return "no statistics"
        duration = self._statistics['time']['range']
        charge = self._statistics['accumulators']['charge']
        energy = self._statistics['accumulators']['energy']
        duration_str = f"{int(duration['value'][0])} {duration['units']}"
        charge_str = three_sig_figs(charge['value'], charge['units'])
        energy_str = three_sig_figs(energy['value'], energy['units'])
        msg = f'duration = {duration_str}, charge = {charge_str}, energy = {energy_str}'
        return msg

    def _display_run_info(self, args):
        if args.duration:
            print(f'Accumulation in progress for {args.duration} seconds.')
        else:
            print('Accumulation in progress.')
        print(f'Updates displayed every {args.update} seconds.')
        print('Press CTRL-C to stop.\n')

    def _run_stream_buffer(self, args):
        device = scan_require_one(config='auto')
        device.parameter_set('buffer_duration', 1)
        signal.signal(signal.SIGINT, self._on_user_exit)
        with device:
            device.statistics_callback = self._on_statistics
            device.start(stop_fn=self._on_stop, duration=args.duration)
            self._display_run_info(args)
            while not self._quit:
                time.sleep(0.01)

    def _run_sensor(self, args):
        device = scan_require_one(config='off')
        device.statistics_callback_register(self._on_statistics, 'sensor')
        with device:
            device.parameter_set('i_range', 'auto')
            device.parameter_set('v_range', '15V')
            self._display_run_info(args)
            while not self._quit:
                device.status()
                time.sleep(0.1)

    def run(self):
        args = get_parser().parse_args()
        self._update_interval = args.update
        if args.source == 'stream_buffer':
            self._run_stream_buffer(args)
        elif args.source == 'sensor':
            self._run_sensor(args)

        print(self._statistics_to_user_str())
        return 0


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s %(message)s', level=logging.WARNING)
    Accumulators().run()
