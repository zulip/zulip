#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from typing import Any, Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
from scripts.lib.setup_path import setup_path

setup_path()

from scripts.lib.zulip_tools import get_config_file

def print_shard(f: Any, host: str, port: str) -> None:
    f.write("""if ($host = '%s') {
    set $tornado_server http://tornado%s;
}\n""" % (host, port))

# Basic system to do Tornado sharding.  Writes two output files:
# * /etc/zulip/nginx_sharding.conf; nginx needs to be reloaded after changing.
# * /etc/zulip/sharding.json; supervisor Django process needs to be reloaded
# after changing.  TODO: We can probably make this live-reload by statting the file.
#
# TODO: Restructure this to automatically generate a sharding layout.
with open('/etc/zulip/nginx_sharding.conf', 'w') as nginx_sharding_conf_f, \
        open('/etc/zulip/sharding.json', 'w') as sharding_json_f:

    config_file = get_config_file()
    if not config_file.has_section("tornado_sharding"):
        nginx_sharding_conf_f.write("set $tornado_server http://tornado;\n")
        sharding_json_f.write('{}\n')
        sys.exit(0)

    nginx_sharding_conf_f.write("set $tornado_server http://tornado9800;\n")
    shard_map: Dict[str, int] = {}
    external_host = subprocess.check_output([os.path.join(BASE_DIR, 'scripts/get-django-setting'),
                                             'EXTERNAL_HOST'],
                                            universal_newlines=True).strip()
    for port in config_file["tornado_sharding"]:
        shards = config_file["tornado_sharding"][port].strip().split(' ')

        for shard in shards:
            if '.' in shard:
                host = shard
            else:
                host = "{}.{}".format(shard, external_host)
            assert host not in shard_map
            shard_map[host] = int(port)
            print_shard(nginx_sharding_conf_f, host, port)
            if shard in ['zephyr', 'recurse']:
                print_shard(nginx_sharding_conf_f, shard + ".zulipstaging.com", port)
        nginx_sharding_conf_f.write('\n')

    sharding_json_f.write(json.dumps(shard_map) + '\n')
