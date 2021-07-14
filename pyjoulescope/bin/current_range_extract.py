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

"""
Extract the current range from a Joulescope JLS capture.

This script opens a JLS capture and extracts the current range data.
The script can save the current range data to another format and plot the
data.  To use this script you will need Python 3.6+ installed on your machine.

To install the required dependencies:

    pip3 install joulescope matplotlib
    
To run this script and get help:

    python3 current_range_extract.py --help
    
Example to save to .txt file:

    python3 current_range_extract.py {my.jls} --out my.txt
    
Example to immediately plot the current range data:

    python3 current_range_extract.py {my.jls} --plot

"""


from joulescope.data_recorder import DataReader
import matplotlib.pyplot as plt
import argparse
import numpy as np
import sys


MAX_SAMPLES = 1000000000 / 5  # limit to 1 GB of RAM


def get_parser():
    p = argparse.ArgumentParser(
        description='Extract the current range from a Joulescope JLS capture.')
    p.add_argument('filename',
                   help='The filename containing the JLS capture.')
    p.add_argument('--out', '-o',
                   help='The output filename')
    p.add_argument('--plot',
                   action='store_true',
                   help='Plot the current range')
    return p


def load_current_range(filename):
    r = DataReader().open(filename)
    try:
        print(r.summary_string())
        r_start, r_stop = r.sample_id_range
        if r_stop - r_start > MAX_SAMPLES:
            print('file too big')
            return 1
        d = r.samples_get(fields=['current_range'])
        return d['signals']['current_range']['value']
    finally:
        r.close()


def run():
    parser = get_parser()
    args = parser.parse_args()
    current_range = load_current_range(args.filename)
    
    # Save file (if requested) in format specified by extension
    if args.out is None:
        pass
    elif args.out.endswith('.csv') or args.out.endswith('.txt'):
        np.savetxt(args.out, current_range, fmt='%d', delimiter=',')
    elif args.out.endswith('.npy'):
        np.save(args.out, current_range)
    else:
        print('Unsupported save type: %s', args.out)
        return 1

    if args.plot:
        f = plt.figure()
        ax = f.add_subplot(1, 1, 1)
        ax.plot(current_range)
        plt.show()
        plt.close(f)

    return 0


if __name__ == '__main__':
    sys.exit(run())

