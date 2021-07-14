#!/usr/bin/env python3

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

"""General purpose input and output demo with streaming input mode.

This demo that drives the outputs and streams the inputs along with the
current and voltage.  To configure your Joulescope for this test:

* Connect a resistor 1 kOhm resistor between sensor OUT+ and sensor OUT-.
* Connect GPIO OUT0 to both IN0 and sensor IN+.
* Connect GPIO GND to sensor IN-.
"""

from joulescope import scan_require_one
import time
import numpy as np
import matplotlib.pyplot as plt


def run():
    count = 0
    _quit = False

    def stop_fn(*args, **kwargs):
        nonlocal _quit
        _quit = True

    # do not use config='auto' so that we can set io_voltage first.
    with scan_require_one(name='Joulescope') as js:
        # configure target Joulescope
        js.parameter_set('io_voltage', '3.3V')
        js.parameter_set('voltage_lsb', 'gpi0')
        js.parameter_set('gpo0', '0')
        js.parameter_set('gpo1', '0')
        js.parameter_set('sensor_power', 'on')
        js.parameter_set('source', 'on')
        js.parameter_set('i_range', '18 mA')

        # start data streaming for 1 second, toggle gpo0 with ~20 ms period
        js.start(stop_fn=stop_fn, duration=1.0)
        while not _quit:
            js.parameter_set('gpo0', str(count & 1))
            count += 1
            time.sleep(0.01)

        # analyze the collected voltage_lsb data for edges
        data = js.stream_buffer.samples_get(*js.stream_buffer.sample_id_range, fields=['current', 'voltage_lsb'])
        current = data['signals']['current']['value']
        out0 = data['signals']['voltage_lsb']['value']
        edges_idx = np.nonzero(np.diff(out0))[0]
        edge_count = len(edges_idx)
        print(f'Found {edge_count} out0 edges')

        # and plot the results
        f = plt.figure()
        ax_gpi = f.add_subplot(2, 1, 1)
        ax_gpi.set_ylabel('GPI')
        ax_gpi.grid(True)

        ax_i = f.add_subplot(2, 1, 2, sharex=ax_gpi)
        ax_i.set_ylabel('Current (A)')
        ax_i.grid(True)
        ax_i.set_xlabel('Time (samples)')

        x_lead = 2
        x_lag = 11  # exclusive
        x = np.arange(-x_lead, x_lag)

        for edge_idx in range(edge_count):
            idx = edges_idx[edge_idx]
            if idx < x_lead or idx > len(out0) - x_lag:
                continue
            ax_gpi.plot(x, out0[idx - x_lead:idx + x_lag])
            ax_i.plot(x, current[idx - x_lead:idx + x_lag])

        plt.show()
        plt.close(f)


if __name__ == '__main__':
    run()
