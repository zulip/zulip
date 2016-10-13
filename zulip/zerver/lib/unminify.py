from __future__ import absolute_import

import re
import os.path
import sourcemap
from six.moves import map
from six import text_type

from typing import Dict


class SourceMap(object):
    '''Map (line, column) pairs from generated to source file.'''

    def __init__(self, sourcemap_dir):
        # type: (text_type) -> None
        self._dir = sourcemap_dir
        self._indices = {} # type: Dict[text_type, sourcemap.SourceMapDecoder]

    def _index_for(self, minified_src):
        # type: (text_type) -> sourcemap.SourceMapDecoder
        '''Return the source map index for minified_src, loading it if not
           already loaded.'''
        if minified_src not in self._indices:
            with open(os.path.join(self._dir, minified_src + '.map')) as fp:
                self._indices[minified_src] = sourcemap.load(fp)

        return self._indices[minified_src]

    def annotate_stacktrace(self, stacktrace):
        # type: (text_type) -> text_type
        out = '' # type: text_type
        for ln in stacktrace.splitlines():
            out += ln + '\n'
            match = re.search(r'/static/min/(.+)(\.[0-9a-f]+)\.js:(\d+):(\d+)', ln)
            if match:
                # Get the appropriate source map for the minified file.
                minified_src = match.groups()[0] + '.js'
                index = self._index_for(minified_src)

                gen_line, gen_col = list(map(int, match.groups()[2:4]))
                # The sourcemap lib is 0-based, so subtract 1 from line and col.
                try:
                    result = index.lookup(line=gen_line-1, column=gen_col-1)
                    out += ('       = %s line %d column %d\n' %
                        (result.src, result.src_line+1, result.src_col+1))
                except IndexError:
                    out +=  '       [Unable to look up in source map]\n'

            if ln.startswith('    at'):
                out += '\n'
        return out
