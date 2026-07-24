"""This module is preloaded into the multiprocessing forkserver by
zerver.lib.parallel.run_parallel_queue, so that worker processes are
forked with Django already set up, and do not each pay to re-import
it.  Setting up Django can itself open connections (e.g. to
memcached); close them, so that the workers do not share them.
"""

import django

django.setup()

from zerver.lib.parallel import _disconnect

_disconnect()
