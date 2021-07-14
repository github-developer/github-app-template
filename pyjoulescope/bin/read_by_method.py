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

"""Use the read() method to get data from Joulescope.

The read method is great for getting short durations of data from Joulescope.
For longer durations, use the stream processes as shown in the
read_by_callback.py example.
"""

from joulescope_examples.plot_cal import plot_iv, print_stats
from joulescope import scan_require_one
import argparse
import logging


DURATION_MAX = 120  # in seconds


def float_or_none(x):
    if x is None:
        return None
    return float(x)


def get_parser():
    p = argparse.ArgumentParser(
        description='Read data from Joulescope.')
    p.add_argument('--duration', '-d',
                   type=float_or_none,
                   help='The capture duration in seconds.')
    p.add_argument('--contiguous', '-c',
                   type=float_or_none,
                   help='The contiguous capture duration in seconds (no missing samples).')
    p.add_argument('--plot',
                   action='store_true',
                   help='Plot the captured data.  Not recommend for captures longer than 1 second!')
    return p


def run():
    args = get_parser().parse_args()
    buffer_duration = args.contiguous
    if buffer_duration is None:
        buffer_duration = args.duration
    if buffer_duration is not None:
        if buffer_duration > DURATION_MAX:
            print(f'To capture more than {DURATION_MAX} seconds, see the read_by_callback.py example')
            return

    device = scan_require_one(config='auto')
    if buffer_duration is not None:
        # adjust the stream buffer size to accommodate this capture
        device.parameter_set('buffer_duration', round(buffer_duration * 1.01 + 0.501))

    # Perform the data capture
    with device:
        device.stream_buffer.suppress_mode = 'off'
        logging.info('read start')
        data = device.read(duration=args.duration, contiguous_duration=args.contiguous)
        logging.info('read done')
    print_stats(data, device.sampling_frequency)

    if args.plot:
        plot_iv(data, device.sampling_frequency)

    return 0


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s %(message)s', level=logging.INFO)
    run()
