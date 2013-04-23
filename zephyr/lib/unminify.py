from __future__ import absolute_import

import re
import bisect
import simplejson
import collections
from os import path

from django.conf import settings


## Un-concatenating source files

class LineToFile(object):
    '''Map line numbers in the concatencated source files to
       individual file/line pairs.'''
    def __init__(self):
        self._names             = []
        self._cumulative_counts = []

        total = 0
        for filename in settings.PIPELINE_JS['app']['source_filenames']:
            self._names.append(filename)
            self._cumulative_counts.append(total)
            with open(path.join('zephyr/static', filename), 'r') as fil:
                total += sum(1 for ln in fil) + 1

    def __call__(self, total):
        i = bisect.bisect_right(self._cumulative_counts, total) - 1
        return (self._names[i], total - self._cumulative_counts[i])

line_to_file = LineToFile()


## Parsing source maps

# Mapping from Base64 digits to numerical value
digits = dict(zip(
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/',
    range(64)))

def parse_base64_vlq(input_str):
    '''Interpret a sequence of Base64 digits as sequence of integers
       in VLQ encoding.'''
    accum, shift = 0, 0
    for digit in input_str:
        value = digits[digit]

        # Low 5 bits provide the next 5 more significant
        # bits of the output value.
        accum |= (value & 0b11111) << shift
        shift += 5

        # Top bit is cleared if this is the last digit
        # for this output value.
        if not value & 0b100000:
            # Bottom bit of the result is sign.
            sign = -1 if accum & 1 else 1
            yield sign * (accum >> 1)
            accum, shift = 0, 0

Link = collections.namedtuple('Link',
    ['src_line', 'src_col', 'gen_line', 'gen_col'])

def parse_mapping(mapstr):
    '''Parse a source map v3 mapping string into a sequence of
       'links' between source and generated code.'''

    fields = [0,0,0,0,0]
    for genline_no, group in enumerate(mapstr.split(';')):
        # The first field (generated code starting column)
        # resets for every group.
        fields[0] = 0
        for segment in group.split(','):
            # Each segment contains VLQ-encoded deltas to the fields.
            delta = list(parse_base64_vlq(segment))
            delta += [0] * (5-len(delta))
            fields = [x+y for x,y in zip(fields, delta)]

            # fields[1] indicates which source file produced this
            # code, but Pipeline concatenates all files together,
            # so this field is always 0.

            # Lines and columns are numbered from zero.
            yield Link(src_line=fields[2],  src_col=fields[3],
                       gen_line=genline_no, gen_col=fields[0])


## Performing the lookup

class SourceMap(object):
    '''Map (line,column) pairs from generated to source file.'''
    def __init__(self, sourcemap_file):
        with open(sourcemap_file, 'r') as fil:
            sourcemap = simplejson.load(fil)

        # Pair each link with a sort / search key
        self._links = [ ((link.gen_line, link.gen_col), link)
            for link in parse_mapping(sourcemap['mappings']) ]
        self._links.sort(key = lambda p: p[0])
        self._keys = [p[0] for p in self._links]

    def _map_position(self, gen_line, gen_col):
        i = bisect.bisect_right(self._keys, (gen_line, gen_col))
        if not i:
            # Zero index indicates no match
            return None

        link = self._links[i-1][1]
        filename, src_line = line_to_file(link.src_line)
        src_col = link.src_col + (gen_col - link.gen_col)

        return (filename, src_line, src_col)

    def annotate_stacktrace(self, stacktrace):
        out = ''
        for ln in stacktrace.splitlines():
            out += ln + '\n'
            match = re.search(r'/static/min/app(\.[0-9a-f]+)?\.js:(\d+):(\d+)', ln)
            if match:
                gen_line, gen_col = map(int, match.groups()[1:3])
                result = self._map_position(gen_line-1, gen_col-1)
                if result:
                    filename, src_line, src_col = result
                    out += ('       = %s line %d column %d\n' %
                        (filename, src_line+1, src_col+1))

            if ln.startswith('    at'):
                out += '\n'
        return out
