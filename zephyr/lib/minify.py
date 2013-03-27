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
        source_map = path.join(settings.PIPELINE_CLOSURE_SOURCE_MAP_DIR,
                               sha1(js).hexdigest() + '.map')

        command = '%s --create_source_map %s' % (
            settings.PIPELINE_CLOSURE_BINARY, source_map)
        return self.execute_command(command, js)
