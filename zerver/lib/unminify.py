
import re
import os
import sourcemap

from typing import Dict, List


class SourceMap:
    '''Map (line, column) pairs from generated to source file.'''

    def __init__(self, sourcemap_dirs: List[str]) -> None:
        self._dirs = sourcemap_dirs
        self._indices = {}  # type: Dict[str, sourcemap.SourceMapDecoder]

    def _index_for(self, minified_src: str) -> sourcemap.SourceMapDecoder:
        '''Return the source map index for minified_src, loading it if not
           already loaded.'''
        if minified_src not in self._indices:
            for source_dir in self._dirs:
                filename = os.path.join(source_dir, minified_src + '.map')
                if os.path.isfile(filename):
                    with open(filename) as fp:
                        self._indices[minified_src] = sourcemap.load(fp)
                        break

        return self._indices[minified_src]

    def annotate_stacktrace(self, stacktrace: str) -> str:
        out = ''  # type: str
        for ln in stacktrace.splitlines():
            out += ln + '\n'
            match = re.search(r'/static/(?:webpack-bundles|min)/(.+)(\.[\.0-9a-f]+\.js):(\d+):(\d+)', ln)
            if match:
                # Get the appropriate source map for the minified file.
                minified_src = match.groups()[0] + match.groups()[1]
                index = self._index_for(minified_src)

                gen_line, gen_col = list(map(int, match.groups()[2:4]))
                # The sourcemap lib is 0-based, so subtract 1 from line and col.
                try:
                    result = index.lookup(line=gen_line-1, column=gen_col-1)
                    display_src = result.src
                    webpack_prefix = "webpack:///"
                    if display_src.startswith(webpack_prefix):
                        display_src = display_src[len(webpack_prefix):]
                    out += ('       = %s line %d column %d\n' %
                            (display_src, result.src_line+1, result.src_col+1))
                except IndexError:
                    out += '       [Unable to look up in source map]\n'

            if ln.startswith('    at'):
                out += '\n'
        return out
