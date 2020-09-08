#!/usr/bin/env python3
import argparse
import hashlib
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


def write_realm_nginx_config_line(f: Any, host: str, port: str) -> None:
    f.write(f"""if ($host = '{host}') {{
    set $tornado_server http://tornado{port};
}}\n""")

def hash_sharding_config() -> str:
    config_file = get_config_file()
    if not config_file.has_section("tornado_sharding"):
        return hashlib.sha256(b'').hexdigest()
    contents = subprocess.check_output([
        "crudini", "--get", "--format=lines", "/etc/zulip/zulip.conf", "tornado_sharding",
    ])
    return hashlib.sha256(contents).hexdigest()

# Basic system to do Tornado sharding.  Writes two output .tmp files that need
# to be renamed to the following files to finalize the changes:
# * /etc/zulip/nginx_sharding.conf; nginx needs to be reloaded after changing.
# * /etc/zulip/sharding.json; supervisor Django process needs to be reloaded
# after changing.  TODO: We can probably make this live-reload by statting the file.
#
# TODO: Restructure this to automatically generate a sharding layout.

parser = argparse.ArgumentParser(description="Adjust Tornado sharding configuration")
parser.add_argument("--verify", action='store_true',
                    help="Exits 0 with no action if no changes are required; exits 1 if changes would be made.")
options = parser.parse_args()

new_hash = hash_sharding_config()
if os.path.exists('/etc/zulip/nginx_sharding.conf') and os.path.exists('/etc/zulip/sharding.json'):
    with open('/etc/zulip/nginx_sharding.conf') as old_file:
        if new_hash in old_file.read():
            sys.exit(0)

if options.verify:
    sys.exit(1)

if "SUPPRESS_SHARDING_NOTICE" not in os.environ:
    print("** Updated sharding; scripts/refresh-sharding-and-restart required")

with open('/etc/zulip/nginx_sharding.conf.tmp', 'w') as nginx_sharding_conf_f, \
        open('/etc/zulip/sharding.json.tmp', 'w') as sharding_json_f:
    # Puppet uses this to know if it needs to rewrite the files
    nginx_sharding_conf_f.write(f"# Configuration hash: {new_hash}\n")

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
                host = f"{shard}.{external_host}"
            assert host not in shard_map, f"host {host} duplicated"
            shard_map[host] = int(port)
            write_realm_nginx_config_line(nginx_sharding_conf_f, host, port)
        nginx_sharding_conf_f.write('\n')

    sharding_json_f.write(json.dumps(shard_map) + '\n')
