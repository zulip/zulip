#!/usr/bin/env python3
import argparse
import filecmp
import json
import os
import subprocess
import sys
from typing import Any, Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
from scripts.lib.setup_path import setup_path

setup_path()

from scripts.lib.zulip_tools import get_config_file, get_tornado_ports


def write_realm_nginx_config_line(f: Any, host: str, port: str) -> None:
    f.write(f"""if ($host = '{host}') {{
    set $tornado_server http://tornado{port};
}}\n""")

# Basic system to do Tornado sharding.  Writes two output .tmp files that need
# to be renamed to the following files to finalize the changes:
# * /etc/zulip/nginx_sharding.conf; nginx needs to be reloaded after changing.
# * /etc/zulip/sharding.json; supervisor Django process needs to be reloaded
# after changing.  TODO: We can probably make this live-reload by statting the file.
#
# TODO: Restructure this to automatically generate a sharding layout.
def write_updated_configs() -> None:
    config_file = get_config_file()
    ports = get_tornado_ports(config_file)

    expected_ports = list(range(9800, max(ports)+1))
    assert sorted(ports) == expected_ports, \
        f"ports ({sorted(ports)}) must be contiguous, starting with 9800"

    with open('/etc/zulip/nginx_sharding.conf.tmp', 'w') as nginx_sharding_conf_f, \
            open('/etc/zulip/sharding.json.tmp', 'w') as sharding_json_f:

        if len(ports) == 1:
            nginx_sharding_conf_f.write("set $tornado_server http://tornado;\n")
            sharding_json_f.write('{}\n')
            return

        nginx_sharding_conf_f.write("set $tornado_server http://tornado9800;\n")
        shard_map: Dict[str, int] = {}
        external_host = subprocess.check_output([os.path.join(BASE_DIR, 'scripts/get-django-setting'),
                                                 'EXTERNAL_HOST'],
                                                universal_newlines=True).strip()
        for port in config_file["tornado_sharding"]:
            shards = config_file["tornado_sharding"][port].strip()

            if shards:
                for shard in shards.split(' '):
                    if '.' in shard:
                        host = shard
                    else:
                        host = f"{shard}.{external_host}"
                    assert host not in shard_map, f"host {host} duplicated"
                    shard_map[host] = int(port)
                    write_realm_nginx_config_line(nginx_sharding_conf_f, host, port)
            nginx_sharding_conf_f.write('\n')

        sharding_json_f.write(json.dumps(shard_map) + '\n')

parser = argparse.ArgumentParser(
    description="Adjust Tornado sharding configuration",
)
parser.add_argument(
    "--errors-ok", action="store_true",
    help="Exits 1 if there are no changes; if there are errors or changes, exits 0."
)
options = parser.parse_args()

config_file_path = "/etc/zulip"
base_files = ['nginx_sharding.conf', 'sharding.json']
full_real_paths = [f"{config_file_path}/{filename}" for filename in base_files]
full_new_paths = [f"{filename}.tmp" for filename in full_real_paths]
try:
    write_updated_configs()
    for old, new in zip(full_real_paths, full_new_paths):
        if not filecmp.cmp(old, new):
            # There are changes; leave .tmp files and exit 0
            if "SUPPRESS_SHARDING_NOTICE" not in os.environ:
                print("===> Updated sharding; run scripts/refresh-sharding-and-restart")
            sys.exit(0)
    # No changes; clean up and exit 1
    for filename in full_new_paths:
        os.unlink(filename)
    sys.exit(1)
except AssertionError as e:
    # Clean up whichever files we made
    for filename in full_new_paths:
        if os.path.exists(filename):
            os.unlink(filename)
    if options.errors_ok:
        sys.exit(0)
    else:
        print(e, file=sys.stderr)
        sys.exit(2)
