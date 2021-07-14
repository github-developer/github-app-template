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

"""Plot calibrated data"""

import matplotlib.pyplot as plt
import matplotlib.collections
import numpy as np
import os
import psutil


def plot_axis(axis, x, y, label=None):
    if label is not None:
        axis.set_ylabel(label)
    axis.grid(True)

    axis.plot(x, y)

    # draw vertical lines at start/end of NaN region
    yvalid = np.isfinite(y)
    for line in x[np.nonzero(np.diff(yvalid))]:
        axis.axvline(line, color='red')

    # Fill each NaN region, too
    ymin, ymax = np.min(y[yvalid]), np.max(y[yvalid])
    collection = matplotlib.collections.BrokenBarHCollection.span_where(
        x, ymin=ymin, ymax=ymax, where=np.logical_not(yvalid), facecolor='red', alpha=0.5)
    axis.add_collection(collection)
    return axis


def plot_iv(data, sampling_frequency, show=None):
    x = np.arange(len(data), dtype=np.float)
    x *= 1.0 / sampling_frequency
    f = plt.figure()

    ax_i = f.add_subplot(2, 1, 1)
    plot_axis(ax_i, x, data[:, 0], label='Current (A)')
    ax_v = f.add_subplot(2, 1, 2, sharex=ax_i)
    plot_axis(ax_v, x, data[:, 1], label='Voltage (V)')

    if show is None or bool(show):
        plt.show()
        plt.close(f)


def memory():
    return psutil.Process(os.getpid()).memory_info().rss  # in bytes


def print_stats(data, sampling_frequency):
    mem = memory() / 2e6
    print(f'Memory usage: {mem:.1f} MB')
    is_finite = np.isfinite(data[:, 0])
    duration = len(data) / sampling_frequency
    finite = np.count_nonzero(is_finite)
    total = len(data)
    nonfinite = total - finite
    print(f'found {nonfinite} NaN out of {total} samples ({duration:.3f} seconds)')
    is_finite[0], is_finite[-1] = True, True  # force counting at start and end
    nan_edges = np.nonzero(np.diff(is_finite))[0]
    nan_runs = len(nan_edges) // 2
    if nan_runs:
        print(f'nan edges: {nan_edges.reshape((-1, 2))}')
        nan_edge_lengths = nan_edges[1::2] - nan_edges[0::2]
        run_mean = np.mean(nan_edge_lengths)
        run_std = np.std(nan_edge_lengths)
        run_min = np.min(nan_edge_lengths)
        run_max = np.max(nan_edge_lengths)
        print(f'found {nan_runs} NaN runs: {run_mean} mean, {run_std} std, {run_min} min, {run_max} max')
