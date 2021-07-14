#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2021 Jetperch LLC
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

"""Report charge & energy over windows when IN0=1.

Caution: the windows must be shorter than the stream buffer duration.
"""

from joulescope import scan_require_one
from joulescope.stream_buffer import stats_to_api
import argparse
import logging
import numpy as np
import signal
import time
import datetime


SAMPLE_COUNT_MIN = 10
CSV_HEADER = '#utc_timestamp,duration(s),charge(C),energy(J)'


def get_parser():
    p = argparse.ArgumentParser(
        description='Report charge & energy over windows when IN0=1.')
    p.add_argument('--io_voltage', '-v',
                   default=3.3,
                   type=float,
                   help='The GPIO voltage.')
    p.add_argument('--out', '-o',
                   help='The output CSV filename.')
    return p


class WindowDetect:

    def __init__(self, filename=None):
        self.sample_id_last = None
        self.sample_id_start = None
        self.sample_id_end = None
        self.timestamp = None
        self._filehandle = None
        if filename is not None:
            self._filehandle = open(filename, 'wt')
            self._filehandle.write(CSV_HEADER + '\n')
    
    def close(self):
        if self._filehandle:
            self._filehandle.close()
            self._filehandle = None
    
    def _process(self, stream_buffer, start_id, end_id):
        d_id = end_id - start_id
        if d_id < SAMPLE_COUNT_MIN:
            return  # too short, debounced
        s = stream_buffer.statistics_get(start_id, end_id)[0]
        t_start = start_id / stream_buffer.output_sampling_frequency
        t_end = end_id / stream_buffer.output_sampling_frequency
        s = stats_to_api(s, t_start, t_end)
        duration = s['time']['delta']['value']
        charge = s['signals']['current']['∫']['value']
        energy = s['signals']['power']['∫']['value']
        timestamp = datetime.datetime.utcfromtimestamp(self.timestamp)
        timestamp_str = timestamp.isoformat()
        line = f'{timestamp_str},{duration:.6f},{charge},{energy}'
        print(line)
        if self._filehandle is not None:
            self._filehandle.write(line + '\n')
            self._filehandle.flush()
        
    def __call__(self, stream_buffer):
        start_id, end_id = stream_buffer.sample_id_range
        if start_id >= end_id:
            return  # nothing to process
        if self.sample_id_last is None:
            self.sample_id_last = start_id
        elif self.sample_id_last >= end_id:
            return  # nothing to process
        gpi = stream_buffer.samples_get(self.sample_id_last, end_id, fields='current_lsb')
        while start_id < end_id:
            start_id_enter = start_id
            if self.sample_id_start is None:  # not triggered
                if np.any(gpi):  # found trigger
                    self.sample_id_start = self.sample_id_last + int(np.argmax(gpi))
                    sample_delta = end_id - self.sample_id_start
                    self.timestamp = time.time() - sample_delta / stream_buffer.output_sampling_frequency
                    start_id = self.sample_id_start
                else:
                    start_id = end_id
            elif not np.all(gpi):  # found end of trigger
                self.sample_id_end = self.sample_id_last + int(np.argmin(gpi))
                self._process(stream_buffer, self.sample_id_start, self.sample_id_end)
                self.sample_id_start = None  # reset trigger
                start_id = self.sample_id_end
            else:
                start_id = end_id
            samples_consumed = start_id - start_id_enter
            gpi = gpi[samples_consumed:]
            self.sample_id_last = start_id


def run():
    _quit = False

    def on_stop(*args, **kwargs):
        nonlocal _quit
        _quit = True

    args = get_parser().parse_args()
    device = scan_require_one(config='auto')
    signal.signal(signal.SIGINT, on_stop)
    window_detect = WindowDetect(args.out)
    gpo = 0
    gpo_count = 0

    # Perform the data capture
    with device:
        device.parameter_set('current_lsb', 'gpi0')
        device.parameter_set('io_voltage', f'{args.io_voltage:.1f}V')
        device.parameter_set('gpo0', gpo)
        device.parameter_set('gpo1', '1')
        device.start(stop_fn=on_stop)
        print('Detecting triggers.  Press CTRL-C to exit.')
        print(CSV_HEADER)
        while not _quit:
            time.sleep(0.1)
            gpo_count += 1
            if gpo_count >= 10:
                gpo = 0 if gpo else 1
                device.parameter_set('gpo0', gpo)
                gpo_count = 0
            window_detect(device.stream_buffer)
            
        device.stop()  # for CTRL-C handling (safe for duplicate calls)
        window_detect.close()
    return 0


if __name__ == '__main__':
    # logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s %(message)s', level=logging.INFO)
    run()
