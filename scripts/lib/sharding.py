#!/usr/bin/env python3
import argparse
import filecmp
import json
import os
import subprocess
import sys
from typing import Dict, List, Tuple, Union

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
from scripts.lib.setup_path import setup_path

setup_path()

from scripts.lib.zulip_tools import get_config_file, get_tornado_ports


def nginx_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# Basic system to do Tornado sharding.  Writes two output .tmp files that need
# to be renamed to the following files to finalize the changes:
# * /etc/zulip/nginx_sharding_map.conf; nginx needs to be reloaded after changing.
# * /etc/zulip/sharding.json; supervisor Django process needs to be reloaded
# after changing.  TODO: We can probably make this live-reload by statting the file.
#
# TODO: Restructure this to automatically generate a sharding layout.
def write_updated_configs() -> None:
    config_file = get_config_file()
    ports = get_tornado_ports(config_file)

    expected_ports = list(range(9800, ports[-1] + 1))
    assert ports == expected_ports, f"ports ({ports}) must be contiguous, starting with 9800"

    with open("/etc/zulip/nginx_sharding_map.conf.tmp", "w") as nginx_sharding_conf_f, open(
        "/etc/zulip/sharding.json.tmp", "w"
    ) as sharding_json_f:
        if len(ports) == 1:
            nginx_sharding_conf_f.write('map "" $tornado_server {\n')
            nginx_sharding_conf_f.write("    default http://tornado;\n")
            nginx_sharding_conf_f.write("}\n")
            sharding_json_f.write("{}\n")
            return

        nginx_sharding_conf_f.write("map $http_host $tornado_server {\n")
        nginx_sharding_conf_f.write("    default http://tornado9800;\n")
        shard_map: Dict[str, Union[int, List[int]]] = {}
        shard_regexes: List[Tuple[str, Union[int, List[int]]]] = []
        external_host = subprocess.check_output(
            [os.path.join(BASE_DIR, "scripts/get-django-setting"), "EXTERNAL_HOST"],
            text=True,
        ).strip()
        for key, shards in config_file["tornado_sharding"].items():
            if key.endswith("_regex"):
                ports = [int(port) for port in key[: -len("_regex")].split("_")]
                shard_regexes.append((shards, ports[0] if len(ports) == 1 else ports))
                nginx_sharding_conf_f.write(
                    f"    {nginx_quote('~*' + shards)} http://tornado{'_'.join(map(str, ports))};\n"
                )
            else:
                ports = [int(port) for port in key.split("_")]
                for shard in shards.split():
                    if "." in shard:
                        host = shard
                    else:
                        host = f"{shard}.{external_host}"
                    assert host not in shard_map, f"host {host} duplicated"
                    shard_map[host] = ports[0] if len(ports) == 1 else ports
                    nginx_sharding_conf_f.write(
                        f"    {nginx_quote(host)} http://tornado{'_'.join(map(str, ports))};\n"
                    )
            nginx_sharding_conf_f.write("\n")
        nginx_sharding_conf_f.write("}\n")

        data = {"shard_map": shard_map, "shard_regexes": shard_regexes}
        sharding_json_f.write(json.dumps(data) + "\n")


parser = argparse.ArgumentParser(
    description="Adjust Tornado sharding configuration",
)
parser.add_argument(
    "--errors-ok",
    action="store_true",
    help="Exits 1 if there are no changes; if there are errors or changes, exits 0.",
)
options = parser.parse_args()

config_file_path = "/etc/zulip"
base_files = ["nginx_sharding_map.conf", "sharding.json"]
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
