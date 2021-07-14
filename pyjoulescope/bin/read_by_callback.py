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

"""Use the stream process callbacks to get data from Joulescope."""

from joulescope_examples.plot_cal import plot_iv, print_stats
from joulescope import scan_require_one
import argparse
import logging
import numpy as np
import signal
import time


def get_parser():
    p = argparse.ArgumentParser(
        description='Read data from Joulescope.')
    p.add_argument('--duration', '-d',
                   default=1.0,
                   type=float,
                   help='The capture duration in seconds.')
    p.add_argument('--plot',
                   action='store_true',
                   help='Plot the captured data.  Not recommend for captures longer than 1 second!')
    return p


class StreamProcess:
    """Receive and store streaming Joulescope data."""

    def __init__(self, duration, sampling_frequency):
        samples = int(duration * sampling_frequency)
        self.chunk_size = 10000
        length = ((samples + self.chunk_size - 1) // self.chunk_size) * self.chunk_size
        self._buffer = np.empty((length, 2), dtype=np.float32)
        self._buffer[:] = 0.0  # force python & OS to allocate the memory
        self.idx = 0

    def __str__(self):
        return 'StreamProcess'

    @property
    def data(self):
        return self._buffer[:self.idx, :]

    def stream_notify(self, stream_buffer):
        # called from USB thead, keep fast!
        # long-running operations will cause sample drops
        start_id, end_id = stream_buffer.sample_id_range
        idx_next = self.idx + self.chunk_size
        while idx_next <= end_id and idx_next <= len(self._buffer):
            # only get and store what we need
            data = stream_buffer.samples_get(self.idx, idx_next, fields=['current', 'voltage'])
            self._buffer[self.idx:idx_next, 0] = data['signals']['current']['value']
            self._buffer[self.idx:idx_next, 1] = data['signals']['voltage']['value']
            self.idx = idx_next
            idx_next += self.chunk_size


def run():
    _quit = False

    def on_stop(*args, **kwargs):
        nonlocal _quit
        _quit = True

    args = get_parser().parse_args()
    device = scan_require_one(config='auto')
    device.parameter_set('buffer_duration', 2)  # could be smaller
    stream_process = StreamProcess(args.duration, device.sampling_frequency)

    signal.signal(signal.SIGINT, on_stop)

    # Perform the data capture
    with device:
        device.stream_process_register(stream_process)
        device.start(stop_fn=on_stop, duration=args.duration)
        while not _quit:
            time.sleep(0.1)
        device.stop()  # for CTRL-C handling (safe for duplicate calls)
    data = stream_process.data
    print_stats(data, device.sampling_frequency)

    if args.plot:
        plot_iv(data, device.sampling_frequency)

    return 0


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s %(message)s', level=logging.INFO)
    run()
