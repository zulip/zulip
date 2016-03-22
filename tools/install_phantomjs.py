
#!/usr/bin/env python2.7
from __future__ import print_function
import os
import sys
import platform

try:
    import sh
except ImportError:
    import pbs as sh

LOUD = dict(_out=sys.stdout, _err=sys.stderr)


def install_phantomjs():
    if platform.architecture()[0] == '64bit':
        phantomjs_arch = 'x86_64'
    elif platform.architecture()[0] == '32bit':
        phantomjs_arch = 'i686'

    with sh.sudo:
        PHANTOMJS_PATH = "/srv/phantomjs"
        PHANTOMJS_BASENAME = "phantomjs-1.9.8-linux-%s" % (phantomjs_arch,)
        PHANTOMJS_TARBALL_BASENAME = PHANTOMJS_BASENAME + ".tar.bz2"
        PHANTOMJS_TARBALL = os.path.join(PHANTOMJS_PATH, PHANTOMJS_TARBALL_BASENAME)
        PHANTOMJS_URL = "https://bitbucket.org/ariya/phantomjs/downloads/%s" % (PHANTOMJS_TARBALL_BASENAME,)
        sh.mkdir("-p", PHANTOMJS_PATH, **LOUD)
        if not os.path.exists(PHANTOMJS_TARBALL):
            sh.wget(PHANTOMJS_URL, output_document=PHANTOMJS_TARBALL, **LOUD)
        sh.tar("xj", directory=PHANTOMJS_PATH, file=PHANTOMJS_TARBALL, **LOUD)
        sh.ln("-sf", os.path.join(PHANTOMJS_PATH, PHANTOMJS_BASENAME, "bin", "phantomjs"),
              "/usr/local/bin/phantomjs", **LOUD)


if __name__ == "__main__":
    install_phantomjs()
