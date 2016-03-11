#!/usr/bin/env python
from __future__ import print_function

# Remove HTML entity escaping left over from MediaWiki->rST conversion.

import html
import sys

for line in sys.stdin:
    print(html.unescape(line), end='')
