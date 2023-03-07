import argparse
import configparser
import os

import digitalocean


def get_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), "conf.ini"))
    return config


parser = argparse.ArgumentParser(description="Clean up old A / AAAA records in zulipdev.org")
parser.add_argument("--force", action="store_true")

if __name__ == "__main__":
    args = parser.parse_args()

    config = get_config()
    api_token = config["digitalocean"]["api_token"]

    seen_ips = set()
    if not args.force:
        print("WOULD DELETE:")

    manager = digitalocean.Manager(token=api_token)
    my_droplets = manager.get_all_droplets()
    for droplet in my_droplets:
        seen_ips.add(droplet.ip_address)
        if droplet.ipv6:
            seen_ips.update(net["ip_address"] for net in droplet.networks["v6"])

    domain = digitalocean.Domain(token=api_token, name="zulipdev.org")
    domain.load()
    records = domain.get_records()

    for record in sorted(records, key=lambda e: ".".join(reversed(e.name.split(".")))):
        if record.type not in ("AAAA", "A"):
            continue
        elif record.data in seen_ips:
            continue
        else:
            print(f"{record.type} {record.name} = {record.data}")
            if args.force:
                record.destroy()

    if not args.force:
        print("Re-run with --force to delete")
