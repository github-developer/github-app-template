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

"""Configure the current ranging filter and then read() Joulescope data.
"""

from joulescope import scan_require_one


def run():
    device = scan_require_one(config='auto')
    with device:
        # turn filter off just to demonstrate
        device.parameter_set('current_ranging_type', 'off')

        # configure an aggressive filter using single field (recommended way).
        device.parameter_set('current_ranging', 'mean_1_3_1')
        print('read 1: ' + device.parameter_get('current_ranging'))
        device.read(contiguous_duration=0.5)

        # configure a very conservative filter using individual fields
        device.parameter_set('current_ranging_type', 'mean')
        device.parameter_set('current_ranging_samples_pre', 4)
        device.parameter_set('current_ranging_samples_window', 8)
        device.parameter_set('current_ranging_samples_post', 4)
        print('read 2: ' + device.parameter_get('current_ranging'))
        device.read(contiguous_duration=0.5)

        # insert a single NaN on each current range change.
        device.parameter_set('current_ranging', 'nan_0_1_0')
        print('read 3: ' + device.parameter_get('current_ranging'))
        device.read(contiguous_duration=0.5)

    return 0


if __name__ == '__main__':
    run()
