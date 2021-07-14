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

r"""
Capture downsampled data to a comma-separate values (CSV) file.

This script collects full-rate 2 MHz data from Joulescope, downsamples the data
to 2 Hz, and then records the downsampled data to a CSV file.  The CSV files 
are automatically named and stored under the Documents/joulescope directory. 
On Windows, this will typically be:

    C:\Users\{user_name}\Documents\joulescope\jslog_{YYYYMMDD_hhmmss}_{pid}_{serial_number}.csv

The ".csv" file contains the capture data with columns:

    time,current,voltage,power,charge,energy

All values are in the International System of Units (SI):

    seconds,amperes,volts,watts,coulombs,joules

The script also creates a ".txt" file which contains the state information
for the logging session.
If something happens to the test setup (like the host computer reboots), 
use the "--resume" option to load the configured state for the most
recent session and resume logging. 
Any charge or energy consumed while the test setup was not logging will not 
be recorded to the CSV file.

This implementation handles failure modes including:

* Joulescope reset
* Joulescope unplug/replug
* Temporary loss of USB communication
* Temporary loss of system power (using --resume option)
* Host computer reset (using --resume option)

For long-term logging, even 2 Hz downsampled data can still create too much data:

    2 lines/second * (60 seconds/minute * 60 minutes/hour * 24 hours/day) = 
    172800 lines / day
    
Lines are typically around 80 bytes each which means that this script generates:

    172800 lines/day * 80 bytes/line = 12 MB/day
    12 MB/day * 30.4 days/month = 420 MB/month
    420 MB/month * 12 months/year = 5 GB/year
    
To further reduce the logging rate, use the "--downsample" option.  For example,
"--downsample 120" will log one (1) sample per minute and reduce the overall
file size by a factor of 120.

Here is the example CSV output with the "simple" header and "--downsample 120" for
a 3.3V supply and 1000 Ω resistive load (10.9 mW):

    time,current,voltage,power,charge,energy
    60.0608842,0.00329505,3.2998,0.0108731,0.197703,0.652385
    120.0572884,0.00329549,3.2997,0.0108743,0.395432,1.30484
    180.0513701,0.00329558,3.2998,0.0108748,0.593167,1.95733
    240.0502210,0.00329565,3.2998,0.0108751,0.790906,2.60984
    300.0581367,0.00329583,3.2997,0.0108751,0.988656,3.26234


List of requested future features:
* Specify save path (but can't break resume function!)
* Add higher sample rate (see forum https://forum.joulescope.com/t/joulescope-data-logging/130/10)

"""

import joulescope
from joulescope.data_recorder import DataRecorder
import signal
import argparse
import time
import sys
import os
import datetime
import logging
import json
import weakref
import numpy as np


try:
    from win32com.shell import shell, shellcon
    DOCUMENTS_PATH = shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL, None, 0)
    BASE_PATH = os.path.join(DOCUMENTS_PATH, 'joulescope')

except Exception:
    BASE_PATH = os.path.expanduser('~/Documents/joulescope')


MAX_SAMPLES = 1000000000 / 5  # limit to 1 GB of RAM
CSV_SEEK = 4096
LAST_INITIALIZE = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
USER_NOTIFY_INTERVAL_S = 10.0
FREQUENCIES = [1, 2, 4, 10, 20, 50, 100]
SAMPLING_FREQUENCIES = [2000000, 1000000, 500000, 200000, 100000, 50000,
                        20000, 10000, 5000, 2000, 1000, 500, 200,
                        100, 50, 20, 10]
FLOAT_MAX = np.finfo(np.float).max


def now_str():
    d = datetime.datetime.utcnow()
    s = d.strftime('%Y%m%d_%H%M%S')
    return s


def downsample_type_check(string):
    value = int(string)
    if value < 1:
        raise argparse.ArgumentTypeError('%r must be >= 1' % (string, ))
    return value


def joulescope_count_to_str(count):
    if count == 0:
        return 'no Joulescopes'
    elif count == 1:
        return 'one Joulescope'
    else:
        return f'{count} Joulescopes'


def get_parser():
    p = argparse.ArgumentParser(
        description='Capture downsampled data.')
    p.add_argument('--header',
                   default='simple',
                   choices=['none', 'simple', 'comment'],
                   help='CSV header option.  '
                        '"none" excludes all header information and just includes data.  '
                        '"simple" (default) adds a first line with column labels.  '
                        '"comment" contains multiple lines starting with "#" and also '
                        'inserts events into the CSV file.  ')
    p.add_argument('--resume', '-r',
                   action='store_true',
                   help='Resume the previous capture and append new data.')
    p.add_argument('--downsample', '-d',
                   default=1,
                   type=downsample_type_check,
                   help='The number of frequency samples (2 Hz by default) to '
                        'condense into a single sample. '
                        'For example, "--downsample 120" will write 1 sample '
                        'per minute.')
    p.add_argument('--frequency', '-f',
                   default=2,
                   choices=FREQUENCIES,
                   type=int,
                   help='The base collection frequency in Hz.  Defaults to 2.')
    p.add_argument('--jls', '-j',
                   type=int,
                   choices=SAMPLING_FREQUENCIES,
                   help='Store JLS file with downsampling frequency.')
    p.add_argument('--source', '-s',
                   default='stream_buffer',
                   choices=['stream_buffer', 'sensor'],
                   help='Select the source for the accumulator data.')
    return p


def _find_files():
    flist = []
    for fname in os.listdir(BASE_PATH):
        if fname.startswith('jslog_') and fname.endswith('.txt'):
            flist.append(fname)
    return sorted(flist)


class Logger:
    """The downsampling logger instance.

    :param header: The CSV header format which is one of ['none', 'simple', 'comment']
    :param downsample: The downsampling factor in samples.
        1 performs no downsampling.
        120 records one sample per minute.
        None (default) is equivalent to 1.
    :param frequency: The base frequency, which defaults to 2 Hz.
    :param resume: Use False or None to start a new logging session.
        Provide True to resume the most recent logging session.
    :param jls_sampling_frequency: The sampling frequency for storing JLS files.
        None (default) does not store a JLS file.
    :param source: The statistic data source.
    """
    def __init__(self, header=None, downsample=None, frequency=None, resume=None,
                 jls_sampling_frequency=None, source=None):
        self._start_time_s = None
        self._f_event = None
        self._time_str = None
        self._quit = None
        self._downsample = 1 if downsample is None else int(downsample)
        self._frequency = 2 if frequency is None else int(frequency)
        self.log = logging.getLogger(__name__)
        self._devices = []
        self._user_notify_time_last = 0.0
        self._faults = []
        self._resume = bool(resume)
        self._jls_sampling_frequency = jls_sampling_frequency
        self._source = source
        self._header = header
        self._base_filename = None
        if self._frequency not in FREQUENCIES:
            raise ValueError(f'Unsupported frequency {self._frequency}')

    def __str__(self):
        return f'Logger("{self._time_str}")'

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.close()
        except Exception:
            self.log.exception('While closing during __exit__')

    def _devices_create(self, device_strs):
        for device_str in device_strs:
            self._devices.append(LoggerDevice(self, device_str))

    def _on_resume(self):
        flist = _find_files()
        if not len(flist):
            print('resume specified, but no existing logs found')
            return
        fname = flist[-1]
        base_filename, _ = os.path.splitext(fname)
        self._base_filename = os.path.join(BASE_PATH, base_filename)
        event_filename = self._base_filename + '.txt'
        print('Resuming ' + event_filename)
        with open(event_filename, 'rt') as f:
            for line in f:
                line = line.strip()
                if ' PARAM : ' in line:
                    name, value = line.split(' PARAM : ')[-1].split('=')
                    if name == 'start_time':
                        self._start_time_s = float(value)
                    elif name == 'start_str':
                        self._time_str = value
                    elif name == 'downsample':
                        self._downsample = int(value)
                    elif name == 'frequency':
                        self._frequency = int(value)
                    elif name == 'jls_sampling_frequency':
                        if value in [None, 'None']:
                            value = None
                        else:
                            value = int(value)
                        self._jls_sampling_frequency = value
                    elif name == 'source':
                        self._source = value
                if 'DEVICES ' in line:
                    device_strs = line.split(' DEVICES : ')[-1].split(',')
                    self._devices_create(device_strs)
                if 'LOGGER : RUN' in line:
                    break
        self._f_event = open(event_filename, 'at')
        self.on_event('LOGGER', 'RESUME')

    def open(self):
        self._quit = None
        os.makedirs(BASE_PATH, exist_ok=True)

        if self._resume:
            self._on_resume()
        else:
            self._start_time_s = time.time()
            self._time_str = now_str()
            base_filename = 'jslog_%s_%s' % (self._time_str, os.getpid())
            self._base_filename = os.path.join(BASE_PATH, base_filename)
            event_filename = self._base_filename + '.txt'
            self._f_event = open(event_filename, 'at')
            self.on_event('LOGGER', 'OPEN')
            self.on_event('PARAM', f'start_time={self._start_time_s}')
            self.on_event('PARAM', f'start_str={self._time_str}')
            self.on_event('PARAM', f'downsample={self._downsample}')
            self.on_event('PARAM', f'frequency={self._frequency}')
            self.on_event('PARAM', f'jls_sampling_frequency={self._jls_sampling_frequency}')
            self.on_event('PARAM', f'source={self._source}')

            devices = joulescope.scan()
            device_strs = [str(device) for device in devices]
            if not len(device_strs):
                raise RuntimeError('No Joulescopes found')
            self.log.info('Found %d Joulescopes', len(device_strs))
            self.on_event('DEVICES', ','.join(device_strs))
            print('Found ' + joulescope_count_to_str(len(device_strs)))
            self._devices_create(device_strs)

    def close(self):
        self.on_event('LOGGER', 'CLOSE')
        while len(self._devices):
            self._devices.pop().close()

        if self._f_event is not None:
            self.on_event('LOGGER', 'DONE')
            self._f_event.close()
            self._f_event = None

    def on_quit(self, *args, **kwargs):
        self.on_event('SIGNAL', 'SIGINT QUIT')
        self._quit = 'quit from SIGINT'

    def on_stop(self, device, event=0, message=''):
        # may be called from the Joulescope device thread, keep short!
        self.on_event('SIGNAL', f'STOP ' + str(device))
        if event is not None and event > 0:
            self._faults.append((event, message))
            self._faults.append(('DEVICE_CLOSE', device))

    def on_event(self, name, message):
        if self._f_event is not None:
            d = datetime.datetime.utcnow()
            s = d.strftime('%Y%m%d_%H%M%S.%f')
            s = f'{s} {name} : {message}\n'
            self._f_event.write(s)
            self._f_event.flush()
            if self._header in ['full', 'comment']:
                for device in self._devices:
                    device.write(f'#& {s}')

    def on_event_cbk(self, device, event=0, message=''):
        # called from the Joulescope device thread, keep short!
        self._faults.append((event, message))
        self._faults.append(('DEVICE_CLOSE', device))

    def _open_devices(self, do_notify=True):
        closed_devices = [d for d in self._devices if not d.is_open]
        closed_count = len(closed_devices)
        if closed_count:
            if do_notify:
                time_now = time.time()
                if (self._user_notify_time_last + USER_NOTIFY_INTERVAL_S) <= time_now:
                    self.log.warning('Missing ' + joulescope_count_to_str(closed_count))
                    self._user_notify_time_last = time_now

            all_devices = joulescope.scan()
            for closed_device in closed_devices:
                for all_device in all_devices:
                    if str(closed_device) == str(all_device):
                        closed_device.open(all_device)
                        break
        else:
            self._user_notify_time_last = 0.0
        return closed_count

    def run(self):
        self.on_event('LOGGER', 'RUN')
        signal.signal(signal.SIGINT, self.on_quit)
        try:
            self._open_devices(do_notify=False)
            while not self._quit:
                closed_count = self._open_devices()
                if closed_count:
                    time.sleep(0.25)
                time.sleep(0.1)  # data is received on device's thread
                if self._source == 'sensor':
                    for device in self._devices:
                        device.status()
                while len(self._faults):  # handle faults on our thread
                    event, message = self._faults.pop(0)
                    self.on_event('EVENT', f'{event} {message}')
                    if event == 'DEVICE_CLOSE':
                        message.close()
            for device in self._devices:
                msg = device.stop()
                self.on_event('SUMMARY', msg)
        except Exception as ex:
            self.log.exception('while capturing data')
            self.on_event('FAIL', str(ex))
            return 1


class LoggerDevice:

    def __init__(self, parent, device_str):
        self.is_open = False
        self._parent = weakref.ref(parent)
        self._device_str = device_str
        self._device = None
        self._f_csv = None
        self._jls_recorder = None

        self._last = None  # (all values in csv)
        self._offset = [0.0, 0.0, 0.0]  # [time, charge, energy]
        self._downsample_counter = 0
        self._downsample_state = {
            'µ': np.zeros(3, dtype=np.float),
            'min': np.zeros(1, dtype=np.float),
            'max': np.zeros(1, dtype=np.float),
        }
        self._downsample_state_reset()

    def _downsample_state_reset(self):
        self._downsample_state['µ'][:] = 0.0
        self._downsample_state['min'][:] = FLOAT_MAX
        self._downsample_state['max'][:] = -FLOAT_MAX

    def __str__(self):
        return self._device_str

    @property
    def csv_filename(self):
        sn = self._device_str.split(':')[-1]
        return self._parent()._base_filename + '_' + sn + '.csv'

    def _resume(self):
        fname = self.csv_filename
        if not os.path.isfile(fname):
            return
        sz = os.path.getsize(fname)
        self._last = LAST_INITIALIZE
        with open(fname, 'rt') as f:
            f.seek(max(0, sz - CSV_SEEK))
            for line in f.readlines()[-1::-1]:
                if line.startswith('#'):
                    continue
                self._last = tuple([float(x) for x in line.strip().split(',')])
                self._offset = [0.0, self._last[-2], self._last[-1]]
                return

    def open(self, device):
        if self.is_open:
            return
        if str(device) != str(self):
            raise ValueError('Mismatch device')
        parent = self._parent()
        parent.on_event('DEVICE', 'OPEN ' + self._device_str)
        self._resume()
        self._f_csv = open(self.csv_filename, 'at+')
        f = parent._frequency
        source = parent._source
        device.parameter_set('reduction_frequency', f'{f} Hz')
        jls_sampling_frequency = parent._jls_sampling_frequency
        if jls_sampling_frequency is not None:
            device.parameter_set('sampling_frequency', jls_sampling_frequency)
        device.parameter_set('buffer_duration', 2)
        device.open(event_callback_fn=self.on_event_cbk)
        if jls_sampling_frequency is not None:
            time_str = now_str()
            base_filename = 'jslog_%s_%s.jls' % (time_str, device.device_serial_number)
            filename = os.path.join(BASE_PATH, base_filename)
            self._jls_recorder = DataRecorder(filename, calibration=device.calibration)
            device.stream_process_register(self._jls_recorder)
        info = device.info()
        self._parent().on_event('DEVICE_INFO', json.dumps(info))
        device.statistics_callback_register(self.on_statistics, source)
        device.parameter_set('i_range', 'auto')
        device.parameter_set('v_range', '15V')
        if source == 'stream_buffer' or jls_sampling_frequency is not None:
            device.parameter_set('source', 'raw')
            device.start(stop_fn=self.on_stop)
        self._device = device
        self.is_open = True
        return self

    def stop(self):
        try:
            if self._device is not None:
                self._device.stop()
            if self._jls_recorder is not None:
                self._device.stream_process_unregister(self._jls_recorder)
                self._jls_recorder.close()
                self._jls_recorder = None
        except Exception:
            pass
        charge, energy = self._last[4], self._last[5]
        msg = f'{self._device} : duration={self.duration:.0f}, charge={charge:g}, energy={energy:g}'
        print(msg)
        return msg

    def on_event_cbk(self, event=0, message=''):
        self._parent().on_event_cbk(self, event, message)

    def on_stop(self, event=0, message=''):
        self._parent().on_stop(self, event, message)

    def close(self):
        self._last = None
        self.is_open = False
        if self._device is not None:
            self._device.close()
            self._device = None
        if self._f_csv is not None:
            self._f_csv.close()
            self._f_csv = None

    def write(self, text):
        if self._f_csv is not None:
            self._f_csv.write(text)

    def status(self):
        return self._device.status()

    @property
    def duration(self):
        now = time.time()
        t = now - self._parent()._start_time_s + self._offset[0]
        return t

    def on_statistics(self, data):
        """Process the next Joulescope downsampled 2 Hz data.

        :param data: The Joulescope statistics data.
            See :meth:`joulescope.View.statistics_get` for details.
        """
        # called from the Joulescope device thread
        parent = self._parent()
        if self._last is None:
            self._last = LAST_INITIALIZE

            columns = ['time', 'current', 'voltage', 'power', 'charge',
                       'energy', 'current_min', 'current_max']
            units = ['s',
                     data['signals']['current']['µ']['units'],
                     data['signals']['voltage']['µ']['units'],
                     data['signals']['power']['µ']['units'],
                     data['accumulators']['charge']['units'],
                     data['accumulators']['energy']['units'],
                     data['signals']['current']['µ']['units'],
                     data['signals']['current']['µ']['units'],
                     ]
            columns_csv = ','.join(columns)
            units_csv = ','.join(units)
            parent.on_event('PARAM', f'columns={columns_csv}')
            parent.on_event('PARAM', f'units={units_csv}')
            if parent._header in ['simple']:
                self._f_csv.write(f'{columns_csv}\n')
            elif parent._header in ['comment', 'full']:
                self._f_csv.write(f'#= header={columns_csv}\n')
                self._f_csv.write(f'#= units={units_csv}\n')
                self._f_csv.write(f'#= start_time={parent._start_time_s}\n')
                self._f_csv.write(f'#= start_str={parent._time_str}\n')
            self._f_csv.flush()
        t = self.duration
        i = data['signals']['current']['µ']['value']
        v = data['signals']['voltage']['µ']['value']
        p = data['signals']['power']['µ']['value']
        c = data['accumulators']['charge']['value'] + self._offset[1]
        e = data['accumulators']['energy']['value'] + self._offset[2]
        i_min = data['signals']['current']['min']['value']
        i_max = data['signals']['current']['max']['value']
        self._downsample_state['µ'] += [i, v, p]
        self._downsample_state['min'] = np.minimum([i_min], self._downsample_state['min'])
        self._downsample_state['max'] = np.maximum([i_max], self._downsample_state['max'])
        self._downsample_counter += 1
        if self._downsample_counter >= parent._downsample:
            s = self._downsample_state['µ'] / self._downsample_counter
            self._downsample_counter = 0
            self._last = (t, *s, c, e, *self._downsample_state['min'], *self._downsample_state['max'])
            self._downsample_state_reset()
            self._f_csv.write('%.7f,%g,%g,%g,%.4f,%g,%g,%g\n' % self._last)
            self._f_csv.flush()


def run():
    parser = get_parser()
    args = parser.parse_args()
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.WARNING,
        datefmt='%Y-%m-%dT%H:%M:%S')
    print('Starting logging - press CTRL-C to stop')
    with Logger(header=args.header, downsample=args.downsample,
                frequency=args.frequency, resume=args.resume,
                jls_sampling_frequency=args.jls, source=args.source) as logger:
        return logger.run()


if __name__ == '__main__':
    sys.exit(run())
