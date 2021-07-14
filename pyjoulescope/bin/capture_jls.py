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

"""Capture Joulescope samples to a JLS file."""

from joulescope import scan_require_one
from joulescope.data_recorder import DataRecorder
import sys
import signal
import time


def run():
    quit_ = False
    
    def do_quit(*args, **kwargs):
        nonlocal quit_
        quit_ = 'quit from SIGINT'

    def on_stop(event, message):
        nonlocal quit_
        quit_ = 'quit from stop duration'  

    if len(sys.argv) != 2:
        print("usage: python3 capture_jls.py [filename]")
        return 1
    filename = sys.argv[1]
    signal.signal(signal.SIGINT, do_quit)
    device = scan_require_one(config='auto')
    with device:
        recorder = DataRecorder(filename,
                                calibration=device.calibration)
        try:
            device.stream_process_register(recorder)
            data = device.start(stop_fn=on_stop)
            print('Capturing data: type CTRL-C to stop')
            while not quit_:
                time.sleep(0.01)
        finally:
            recorder.close()
    return 0


if __name__ == '__main__':
    run()
