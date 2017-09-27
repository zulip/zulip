#!/usr/bin/env python3

# Remove HTML entity escaping left over from MediaWiki->rST conversion.

import html
import sys

for line in sys.stdin:
    print(html.unescape(line), end='')
