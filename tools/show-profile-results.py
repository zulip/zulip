#!/usr/bin/env python
from __future__ import print_function
import sys
import pstats

'''
This is a helper script to make it easy to show profile
results after using a Python decorator.  It's meant to be
a simple example that you can hack on, or better yet, you
can find more advanced tools for showing profiler results.
'''

try:
    fn = sys.argv[1]
except IndexError:
    print('''
    Please supply a filename.  (If you use the profiled decorator,
    the file will have a suffix of ".profile".)
    ''')
    sys.exit(1)

p = pstats.Stats(fn)  # type: ignore # stats stubs are broken
p.strip_dirs().sort_stats('cumulative').print_stats(25)  # type: ignore # stats stubs are broken
p.strip_dirs().sort_stats('time').print_stats(25)  # type: ignore # stats stubs are broken
