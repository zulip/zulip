#!/usr/bin/env python3
from __future__ import print_function
import re
from collections import defaultdict
import os
import sys
from typing import Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from zerver.lib.user_agent import parse_user_agent

user_agents_parsed = defaultdict(int)  # type: Dict[str, int]
user_agents_path = os.path.join(os.path.dirname(__file__), "user_agents_unique")
parse_errors = 0
for line in open(user_agents_path).readlines():
    line = line.strip()
    match = re.match('^(?P<count>[0-9]+) "(?P<user_agent>.*)"$', line)
    if match is None:
        print(line)
        continue
    groupdict = match.groupdict()
    count = groupdict["count"]
    user_agent = groupdict["user_agent"]
    ret = parse_user_agent(user_agent)
    if ret is None:
        print("parse error", line)
        parse_errors += 1
        continue
    user_agents_parsed[ret["name"]] += int(count)

for key in user_agents_parsed:
    print("    ", key, user_agents_parsed[key])

print("%s parse errors!" % (parse_errors,))
