#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2019-2021 Jetperch LLC
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

"""
Get data from Joulescope over regions of interest.

Example 1: Capture to a single window using IN0 with self-test

    Connect OUT0 to IN0 using a wire.  Then run:
    
    python3 trigger.py --start rising --end falling --csv myout.csv --display_trigger --display_stats --self_test


Example 2: Capture to a single window using IN0

    python3 trigger.py --start rising --end falling --count 1 --record --display_trigger --display_stats


Example 3: Capture to statistics to CSV using IN0

    python3 trigger.py --start rising --end falling --csv myout.csv --display_trigger
    
    
Example 4: Capture data to JLS files

    python3 trigger.py --start rising --end falling --record --display_trigger


Requirements:
1.  Capture data over a window
2.  At end of the window, option to print to screen and/or CSV:
    2a. Mean, min, max for current, voltage, power
    2b. Charge in C and Ah
    2c. Energy in J and Wh
3.  Record window to JLS file (option)
4.  Trigger window capture start on:
    4a. Joulescope GPI0 level low
    4b. Joulescope GPI0 level high
    4c. Joulescope GPI0 edge low → high
    4d. Joulescope GPI0 edge high → low
    4e. After a configurable duration
5.  Configure the current range
6.  Configure voltage range for 5V or 15V
7.  Option to power off device for a configurable duration at the start of the script
8.  Option to power off device at the end of the script
9.  Trigger window capture end on:
    9a. Joulescope GPI0 level low
    9b. Joulescope GPI0 level high
    9c. Joulescope GPI0 edge low → high
    9d. Joulescope GPI0 edge high → low
    9e. After a configurable duration
    9f. CTRL-C
10. Capture numerous windows (defaults to 1)
"""

from joulescope import scan_require_one
from joulescope.data_recorder import DataRecorder
import argparse
import datetime
import logging
import numpy as np
import os
import signal
import time


_quit = False
GAIN = 1e15
log = logging.getLogger()
COLUMNS = 'start_time(samples),start_time(iso),end_time(samples),end_time(iso),' + \
          'current_mean(A),current_min(A),current_max(A),' + \
          'voltage_mean(V),voltage_min(V),voltage_max(V),' + \
          'power_mean(W),power_min(W),power_max(W),' + \
          'charge(C),charge(Ah),' + \
          'energy(J),energy(Wh)'
FIELD_MAP = {'in0': 'current_lsb', 'in1': 'voltage_lsb'}
IO_TRIG = ['low', 'high', 'rising', 'falling']


def get_parser():
    p = argparse.ArgumentParser(
        description='Read data from Joulescope.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('--record', '-r',
                   action='store_true',
                   help='Capture to automatically named JLS files.')
    p.add_argument('--csv',
                   help='Capture each event to this CSV file')
    p.add_argument('--start',
                   default='none',  # immediate
                   choices=['none', 'low', 'high', 'rising', 'falling', 'duration'],
                   help='The starting trigger condition.')
    p.add_argument('--start_signal',
                   default='in0',
                   choices=['in0', 'in1'],
                   help='The starting trigger signal.')
    p.add_argument('--start_duration',
                   default=1.0,
                   type=float,
                   help='The starting trigger duration in seconds, ' +
                        'when start==duration.')
    p.add_argument('--end',
                   default='none',  # CTRL-C only
                   choices=['none', 'low', 'high', 'rising', 'falling', 'duration'],
                   help='The ending trigger condition.')
    p.add_argument('--end_signal',
                   default='in0',
                   choices=['in0', 'in1'],
                   help='The ending trigger signal.')
    p.add_argument('--capture_duration',
                   default=1.0,
                   type=float,
                   help='The capture duration in seconds, ' + 
                        'when end==duration.')
    p.add_argument('--current_range',
                   default='auto',
                   help='The JS110 current range setting.')
    p.add_argument('--voltage_range',
                   help='The JS110 voltage range setting.')
    p.add_argument('--init_power_off',
                   default=0.0,
                   type=float,
                   help='The initial DUT power off duration (power cycle).')
    p.add_argument('--power_off',
                   action='store_true',
                   help='Power off the DUT when done.')
    p.add_argument('--count',
                   default=0,
                   type=int,
                   help='The number of capture cycles to perform.')
    p.add_argument('--io_voltage', '-v',
                   default=3.3,
                   type=float,
                   help='The GPIO voltage.')
    p.add_argument('--display_trigger',
                   action='store_true',
                   help='Display the start and end trigger information.')
    p.add_argument('--display_stats',
                   action='store_true',
                   help='Display the statistics over each trigger window.')
    p.add_argument('--self_test',
                   action='store_true',
                   help='Self-test mode that toggles OUT0.')
    p.add_argument('--sampling_frequency',
                   help='The device sampling frequency.  Default is maximum supported by device.')
    return p


def _current_time_str():
    t = datetime.datetime.utcnow()
    return t.isoformat()


class Signal:
    
    def __init__(self):
        self._mean = 0
        self._min = None
        self._max = None
        self._length = 0
        
    def clear(self):
        self._mean = 0
        self._min = None
        self._max = None
        self._length = 0
        
    def add(self, v):
        self._mean += int(np.sum(v) * GAIN)
        v_min = np.min(v)
        v_max = np.max(v)
        if self._min is None:
            self._min = v_min
            self._max = v_max
        else:
            self._min = min(self._min, v_min)
            self._max = max(self._max, v_max)
        self._length += len(v)
        
    def result(self):
        if self._length <= 0:
            v_mean = None
        else:
            v_mean = self._mean / (GAIN * self._length)
        return [v_mean, self._min, self._max]


class Capture:

    def __init__(self, device, args):
        self._device = device
        self._args = args
        self._timestamp = None
        self._record = None
        self._csv = None
        self._count = 0
        self._triggered = False
        self._sample_id_last = None
        self._start_fn = getattr(self, f'_start_{args.start}')
        self._end_fn = getattr(self, f'_end_{args.end}')
        self._current = Signal()
        self._voltage = Signal()
        self._power = Signal()
        self._charge = 0  # in 1e-15 C, use Python int for infinite precision
        self._energy = 0  # in 1e-15 J, use Python int for infinite precision
        self._time_start = None  # [sample, timestr]
        self._time_end = None
        
        if self._args.csv is not None:
            self._csv = open(self._args.csv, 'wt')
            self._csv.write(f'#{COLUMNS}\n')

    def _construct_record_filename(self):
        time_start = datetime.datetime.utcnow()
        timestamp_str = time_start.strftime('%Y%m%d_%H%M%S')
        return f'{timestamp_str}_{self._count + 1:04d}.jls'

    def start(self, start_id):
        if self._triggered:
            self.stop()
        self._time_start = [start_id, _current_time_str()]
        log.info(f'start {start_id}')
        if self._args.display_trigger:
            print(f'start {start_id}')
        self._current.clear()
        self._voltage.clear()
        self._power.clear()
        self._charge = 0
        self._energy = 0
        if self._args.record:
            filename = self._construct_record_filename()
            self._record = DataRecorder(filename,
                                        calibration=self._device.calibration)
        self._triggered = True
        return start_id

    def stop(self, end_id=None):
        if not self._triggered:
            return
        if end_id is None:
            end_id = self._sample_id_last
        self._time_end = [end_id, _current_time_str()]
        if self._record:
            self._record.close()
            self._record = None
        log.info(f'stop {end_id}')
        if self._args.display_trigger:
            print(f'stop {end_id}')

        self._count += 1
        current = self._current.result()
        voltage = self._voltage.result()
        power = self._power.result()
        charge = self._charge / GAIN
        energy = self._energy / GAIN
        r = self._time_start + self._time_end + \
            current + voltage + power + \
            [charge, charge / 3600.0] + [energy, energy / 3600.0]
        results = []
        for x in r:
            if x is None:
                results.append('NAN')
            elif isinstance(x, int):
                results.append(str(x))
            elif isinstance(x, str):
                results.append(x)
            else:
                results.append('%g' % x)
        line = ','.join(results)
        
        if self._args.display_stats:
            if self._count == 1:
                print(COLUMNS)
            print(line)
        if self._csv is not None:
            self._csv.write(line + '\n')
            self._csv.flush()
        self._triggered = False
        return end_id
        
    def close(self):
        self.stop()
        if self._csv is not None:
            self._csv.close()

    def _in_level_low(self, stream_buffer, field, start_id, end_id):
        field = FIELD_MAP.get(field, field)
        gpi = stream_buffer.samples_get(start_id, end_id, fields=field)
        if not np.all(gpi):  # found trigger
            return start_id + int(np.argmin(gpi))
        return None

    def _in_level_high(self, stream_buffer, field, start_id, end_id):
        field = FIELD_MAP.get(field, field)
        gpi = stream_buffer.samples_get(start_id, end_id, fields=field)
        if np.any(gpi):  # found trigger
            return start_id + int(np.argmax(gpi))
        return None

    def _in_edge_rising(self, stream_buffer, field, start_id, end_id):
        field = FIELD_MAP.get(field, field)
        if start_id <= 0:
            gpi = stream_buffer.samples_get(start_id, end_id, fields=field)
            if bool(gpi[0]):
                return start_id
        else:
            gpi = stream_buffer.samples_get(start_id, end_id, fields=field)
        gpi = gpi.astype(np.int8)
        d = np.diff(gpi)
        if np.any(d >= 1):  # found trigger
            return start_id + int(np.argmax(d))
        return None

    def _in_edge_falling(self, stream_buffer, field, start_id, end_id):
        field = FIELD_MAP.get(field, field)
        if start_id <= 0:
            gpi = stream_buffer.samples_get(start_id, end_id, fields=field)
            if not bool(gpi[0]):
                return start_id
        else:
            gpi = stream_buffer.samples_get(start_id, end_id, fields=field)
        gpi = gpi.astype(np.int8)
        d = np.diff(gpi)
        if np.any(d <= -1):  # found trigger
            return start_id + int(np.argmin(d))
        return None

    def _start_none(self, stream_buffer, start_id, end_id):
        return start_id

    def _start_low(self, stream_buffer, start_id, end_id):
        field = self._args.start_signal
        return self._in_level_low(stream_buffer, field, start_id, end_id)

    def _start_high(self, stream_buffer, start_id, end_id):
        field = self._args.start_signal
        return self._in_level_high(stream_buffer, field, start_id, end_id)

    def _start_rising(self, stream_buffer, start_id, end_id):
        field = self._args.start_signal
        return self._in_edge_rising(stream_buffer, field, start_id, end_id)

    def _start_falling(self, stream_buffer, start_id, end_id):
        field = self._args.start_signal
        return self._in_edge_falling(stream_buffer, field, start_id, end_id)

    def _start_duration(self, stream_buffer, start_id, end_id):
        if self._time_end is None:
            self._time_end = [start_id, _current_time_str()]
        d = int(self._args.start_duration * stream_buffer.output_sampling_frequency)
        d += self._time_end[0]
        if end_id > d:
            return d
        else:
            return None

    def _add(self, stream_buffer, start_id, end_id):
        data = stream_buffer.samples_get(start_id, end_id)
        i_all = data['signals']['current']['value']
        v_all = data['signals']['voltage']['value']
        p_all = data['signals']['power']['value']
        finite_idx = np.isfinite(i_all)
        i, v, p = i_all[finite_idx], v_all[finite_idx], p_all[finite_idx]
        if len(i) != len(i_all):
            print(f'Ignored {len(i_all) - len(i)} missing samples')
        if len(i):
            self._current.add(i)
            self._voltage.add(v)
            self._power.add(p)
            period = 1.0 / stream_buffer.output_sampling_frequency
            self._charge += int(np.sum(i) * period * GAIN)
            self._energy += int(np.sum(p) * period * GAIN)
            if self._record is not None:
                self._record.insert(data)
        return end_id

    def _end_none(self, stream_buffer, start_id, end_id):
        return None

    def _end_low(self, stream_buffer, start_id, end_id):
        field = self._args.end_signal
        return self._in_level_low(stream_buffer, field, start_id, end_id)

    def _end_high(self, stream_buffer, start_id, end_id):
        field = self._args.end_signal
        return self._in_level_high(stream_buffer, field, start_id, end_id)

    def _end_rising(self, stream_buffer, start_id, end_id):
        field = self._args.end_signal
        return self._in_edge_rising(stream_buffer, field, start_id, end_id)

    def _end_falling(self, stream_buffer, start_id, end_id):
        field = self._args.end_signal
        return self._in_edge_falling(stream_buffer, field, start_id, end_id)

    def _end_duration(self, stream_buffer, start_id, end_id):
        d = int(self._args.capture_duration * stream_buffer.output_sampling_frequency)
        d += self._time_start[0]
        if end_id > d:
            return d
        else:
            return None

    def __call__(self, stream_buffer):
        start_id, end_id = stream_buffer.sample_id_range
        if self._sample_id_last is not None and start_id < self._sample_id_last:
            start_id = self._sample_id_last
        if start_id >= end_id:
            return False  # nothing to process

        gpi = stream_buffer.samples_get(start_id, end_id, fields='current_lsb')
        while start_id < end_id:
            if not self._triggered:
                log.info(f'process {start_id} {end_id} await')
                trigger_id = self._start_fn(stream_buffer, start_id, end_id)
                if trigger_id is None:
                    start_id = end_id
                else:
                    self.start(trigger_id)
                    start_id = trigger_id + 1
            else:
                log.info(f'process {start_id} {end_id} triggered')
                trigger_id = self._end_fn(stream_buffer, start_id, end_id)
                if trigger_id is None:
                    self._add(stream_buffer, start_id, end_id)
                    start_id = end_id
                else:
                    if start_id + 2 < trigger_id:
                        self._add(stream_buffer, start_id, trigger_id - 1)
                    self.stop(trigger_id)
                    start_id = trigger_id + 1
            if self._args.count and self._count >= self._args.count:
                return True
            self._sample_id_last = start_id
        self._sample_id_last = end_id
        return False


def _power_off(device, duration):
    global _quit
    if duration <= 0.0:
        return
    device.parameter_set('i_range', 'off')
    stop_time = time.time() + float(duration)
    while not _quit:
        dt = stop_time - time.time()
        if dt <= 0.0:
            return
        elif dt > 0.1:
            dt = 0.1
        time.sleep(dt)


def _on_stop(*args, **kwargs):
    global _quit
    _quit = True


def run():
    args = get_parser().parse_args()
    device = scan_require_one(config='ignore')
    device.parameter_set('buffer_duration', 10)
    if args.sampling_frequency is not None:
        device.parameter_set('sampling_frequency', int(args.sampling_frequency))
    signal.signal(signal.SIGINT, _on_stop)
    gpo = 0
    gpo_count = 0

    # Perform the data capture
    with device:
        device.parameter_set('io_voltage', f'{args.io_voltage:.1f}V')
        device.parameter_set('gpo0', 0)
        device.parameter_set('gpo1', 1)
        if ('in0' in args.start_signal and args.start in IO_TRIG) or ('in0' in args.end_signal and args.end in IO_TRIG):
            device.parameter_set('current_lsb', 'gpi0')
        if ('in1' in args.start_signal and args.start in IO_TRIG) or ('in1' in args.end_signal and args.end in IO_TRIG):
            device.parameter_set('voltage_lsb', 'gpi1')
        capture = Capture(device, args)
        device.parameter_set('source', 'on')
        _power_off(device, args.init_power_off)
        device.parameter_set('i_range', args.current_range)
        if args.voltage_range:
            device.parameter_set('v_range', args.voltage_range)
        device.start(stop_fn=_on_stop)
        while not _quit:
            time.sleep(0.1)
            gpo_count += 1
            if gpo_count >= 10:
                gpo = 0 if gpo else 1
                if args.self_test:
                    device.parameter_set('gpo0', gpo)
                gpo_count = 0
            if capture(device.stream_buffer):
                break
        device.stop()  # for CTRL-C handling (safe for duplicate calls)
        capture.close()
        if args.power_off:
            device.parameter_set('i_range', 'off')
    return 0


if __name__ == '__main__':
    log_level = os.environ.get('JS_LOG_LEVEL', 'WARNING').upper()
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s %(message)s', level=log_level)
    run()
