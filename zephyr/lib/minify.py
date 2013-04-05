from __future__ import absolute_import

from django.conf import settings
from hashlib     import sha1
from os          import path

from pipeline.compressors import SubProcessCompressor

class ClosureSourceMapCompressor(SubProcessCompressor):
    def compress_js(self, js):
        # js is the full text of the JavaScript source, and we can't
        # easily get either the input file names or the output file
        # name.  So we just pick a unique arbitrary name.  This is
        # okay because we can figure out from the source map file
        # contents which JavaScript files it corresponds to.

        # As a hack to make things easier, assume that any large input
        # corresponds to app.js.  This is like 60 times bigger than
        # any other input file, at present.

        if len(js) > 100000:
            source_map_name = 'app.js.map'
        else:
            source_map_name = sha1(js).hexdigest() + '.map'

        source_map = path.join(
            settings.PIPELINE_CLOSURE_SOURCE_MAP_DIR, source_map_name)

        command = '%s --language_in ECMASCRIPT5 --create_source_map %s' % (
            settings.PIPELINE_CLOSURE_BINARY, source_map)
        return self.execute_command(command, js)
