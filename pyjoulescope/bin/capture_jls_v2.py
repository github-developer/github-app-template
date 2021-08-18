#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2020-2021 Jetperch LLC
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

"""Capture Joulescope data to a JLS v2 file.  See https://github.com/jetperch/jls"""

from joulescope import scan_require_one
from pyjls import Writer, SourceDef, SignalDef, SignalType, DataType
import argparse
import numpy as np
import signal
import time


def _duration_validator(d):
    if d is None or not len(d):
        return None
    if d[-1] == 's':
        return float(d[:-1])
    elif d[-1] == 'm':
        return 60 * float(d[:-1])
    elif d[-1] == 'h':
        return 60 * 60 * float(d[:-1])
    elif d[-1] == 'd':
        return 60 * 60 * 24 * float(d[:-1])
    else:
        return float(d)


def _sampling_rate_validator(s):
    if isinstance(s, str):
        n, u = s.split()
        s = int(n)
        if u[0] == 'M':
            s *= 1000000
        elif u[0] == 'k':
            s *= 1000
    return int(s)


def get_parser():
    p = argparse.ArgumentParser(
        description='Capture Joulescope samples to a JLS v2.  See https://github.com/jetperch/jls')
    p.add_argument('--duration',
                   type=_duration_validator,
                   help='The capture duration in float seconds. '
                   + 'Add a suffix for other units: s=seconds, m=minutes, h=hours, d=days')
    p.add_argument('filename',
                   help='The JLS filename to record.')
    return p


def jls_open(args, device):
    info = device.info()
    sampling_rate = device.parameter_get('sampling_frequency')
    sampling_rate = _sampling_rate_validator(sampling_rate)

    source = SourceDef(
        source_id=1,
        name=str(device),
        vendor='Jetperch',
        model=info['ctl']['hw'].get('model', 'JS110'),
        version=info['ctl']['hw'].get('rev', '-'),
        serial_number=info['ctl']['hw']['sn_mfg'],
    )

    i_signal = SignalDef(
        signal_id=1,
        source_id=1,
        signal_type=SignalType.FSR,
        data_type=DataType.F32,
        sample_rate=sampling_rate,
        name='current',
        units='A',
    )

    v_signal = SignalDef(
        signal_id=2,
        source_id=1,
        signal_type=SignalType.FSR,
        data_type=DataType.F32,
        sample_rate=sampling_rate,
        name='voltage',
        units='V',
    )

    wr = Writer(args.filename)
    try:
        wr.source_def_from_struct(source)
        wr.signal_def_from_struct(i_signal)
        wr.signal_def_from_struct(v_signal)
    except Exception:
        wr.close()
        raise

    return wr


class Process:

    def __init__(self, device, jls_writer):
        self._device = device
        self._wr = jls_writer
        self._idx = 0

    def stream_notify(self, stream_buffer):
        # called from USB thead, keep fast!
        # long-running operations will cause sample drops
        start_id, end_id = stream_buffer.sample_id_range
        if self._idx < end_id:
            data = stream_buffer.samples_get(self._idx, end_id, fields=['current', 'voltage'])
            i = np.ascontiguousarray(data['signals']['current']['value'])
            v = np.ascontiguousarray(data['signals']['voltage']['value'])
            self._wr.fsr_f32(1, self._idx, i)
            self._wr.fsr_f32(2, self._idx, v)
            self._idx = end_id


def run():
    quit_ = False
    args = get_parser().parse_args()
    duration = args.duration

    def do_quit(*args, **kwargs):
        nonlocal quit_
        quit_ = 'quit from SIGINT'

    signal.signal(signal.SIGINT, do_quit)
    device = scan_require_one(config='auto')
    with device:
        wr = jls_open(args, device)
        p = Process(device, wr)
        try:
            device.stream_process_register(p)
            t_stop = None if duration is None else time.time() + duration
            device.start()
            print('Capturing data: type CTRL-C to stop')
            while not quit_:
                time.sleep(0.01)
                if t_stop and time.time() > t_stop:
                    break
            device.stop()
        finally:
            wr.close()
    return 0


if __name__ == '__main__':
    run()
