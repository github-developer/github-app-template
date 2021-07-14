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

from joulescope.data_recorder import DataRecorder, DataReader
import argparse
import logging
import sys


def get_parser():
    p = argparse.ArgumentParser(
        description='Read a JLS file and write to a new JLS file using the latest format.')
    p.add_argument('infile',
                   help='The input JLS file path')
    p.add_argument('outfile',
                   help='The output JLS file path')
    return p


def progress(count, total, status=''):
    # The MIT License (MIT)
    # Copyright (c) 2016 Vladimir Ignatev
    #
    # Permission is hereby granted, free of charge, to any person obtaining
    # a copy of this software and associated documentation files (the "Software"),
    # to deal in the Software without restriction, including without limitation
    # the rights to use, copy, modify, merge, publish, distribute, sublicense,
    # and/or sell copies of the Software, and to permit persons to whom the Software
    # is furnished to do so, subject to the following conditions:
    #
    # The above copyright notice and this permission notice shall be included
    # in all copies or substantial portions of the Software.
    #
    # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
    # INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
    # PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
    # FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT
    # OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
    # OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
    #
    # https://gist.github.com/vladignatyev/06860ec2040cb497f0f3
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))
    percents = round(100.0 * count / float(total), 1)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)

    sys.stdout.write('[%s] %s%s ...%s\r' % (bar, percents, '%', status))
    sys.stdout.flush()  # As suggested by Rom Ruben (see: http://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console/27871113#comment50529068_27871113)


def run():
    args = get_parser().parse_args()
    reader = DataReader()
    reader.open(args.infile)
    s_min, s_max = reader.sample_id_range
    sample_count = s_max - s_min
    writer = DataRecorder(args.outfile, reader.calibration, reader.user_data)
    block_size = int(reader.sampling_frequency)
    print(f'samples={sample_count}, fs={reader.sampling_frequency}')
    block_count = (sample_count + block_size - 1) // block_size
    for block in range(block_count):
        offset = block * block_size
        offset_next = offset + block_size
        if offset_next > sample_count:
            offset_next = sample_count
        data = reader.samples_get(offset, offset_next, 'samples')
        writer.insert(data)
        progress(block, block_count - 1)
    reader.close()
    writer.close()
    return 0


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s %(message)s', level=logging.INFO)
    run()
