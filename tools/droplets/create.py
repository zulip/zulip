# Creates a Zulip remote development environment droplet or
# a production droplet in DigitalOcean.
#
# Particularly useful for sprints/hackathons, interns, and other
# situation where one wants to quickly onboard new contributors.
#
# Requires python-digitalocean library:
# https://github.com/koalalorenzo/python-digitalocean
#
# Also requires DigitalOcean team membership for Zulip and API token:
# https://cloud.digitalocean.com/settings/api/tokens
#
# Copy conf.ini-template to conf.ini and populate with your API token.
import argparse
import configparser
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple

import digitalocean
import requests

parser = argparse.ArgumentParser(description="Create a Zulip development VM DigitalOcean droplet.")
parser.add_argument(
    "username", help="GitHub username for whom you want to create a Zulip dev droplet"
)
parser.add_argument("--tags", nargs="+", default=[])
parser.add_argument("-f", "--recreate", action="store_true")
parser.add_argument("-s", "--subdomain")
parser.add_argument("-p", "--production", action="store_true")
parser.add_argument("-r", "--region", choices=("nyc3", "sfo3", "blr1", "fra1"), default="nyc3")


def get_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), "conf.ini"))
    return config


def assert_github_user_exists(github_username: str) -> bool:
    print(f"Checking to see if GitHub user {github_username} exists...")
    user_api_url = f"https://api.github.com/users/{github_username}"
    try:
        response = urllib.request.urlopen(user_api_url)
        json.load(response)
        print("...user exists!")
        return True
    except urllib.error.HTTPError as err:
        print(err)
        print(f"Does the GitHub user {github_username} exist?")
        sys.exit(1)


def get_ssh_public_keys_from_github(github_username: str) -> List[Dict[str, Any]]:
    print("Checking to see that GitHub user has available public keys...")
    apiurl_keys = f"https://api.github.com/users/{github_username}/keys"
    try:
        response = urllib.request.urlopen(apiurl_keys)
        userkeys = json.load(response)
        if not userkeys:
            print(
                f"No keys found. Has user {github_username} added SSH keys to their GitHub account?"
            )
            sys.exit(1)
        print("...public keys found!")
        return userkeys
    except urllib.error.HTTPError as err:
        print(err)
        print(f"Has user {github_username} added SSH keys to their GitHub account?")
        sys.exit(1)


def assert_user_forked_zulip_server_repo(username: str) -> bool:
    print("Checking to see GitHub user has forked zulip/zulip...")
    apiurl_fork = f"https://api.github.com/repos/{username}/zulip"
    try:
        response = urllib.request.urlopen(apiurl_fork)
        json.load(response)
        print("...fork found!")
        return True
    except urllib.error.HTTPError as err:
        print(err)
        print(f"Has user {username} forked zulip/zulip?")
        sys.exit(1)


def assert_droplet_does_not_exist(my_token: str, droplet_name: str, recreate: bool) -> None:
    print(f"Checking to see if droplet {droplet_name} already exists...")
    manager = digitalocean.Manager(token=my_token)
    my_droplets = manager.get_all_droplets()
    for droplet in my_droplets:
        if droplet.name.lower() == droplet_name:
            if not recreate:
                print(
                    f"Droplet {droplet_name} already exists. Pass --recreate if you "
                    "need to recreate the droplet."
                )
                sys.exit(1)
            else:
                print(f"Deleting existing droplet {droplet_name}.")
                droplet.destroy()
                return
    print("...No droplet found...proceeding.")


def get_ssh_keys_string_from_github_ssh_key_dicts(userkey_dicts: List[Dict[str, Any]]) -> str:
    return "\n".join(userkey_dict["key"] for userkey_dict in userkey_dicts)


def generate_dev_droplet_user_data(
    username: str, subdomain: str, userkey_dicts: List[Dict[str, Any]]
) -> str:
    ssh_keys_string = get_ssh_keys_string_from_github_ssh_key_dicts(userkey_dicts)
    setup_root_ssh_keys = f"printf '{ssh_keys_string}' > /root/.ssh/authorized_keys"
    setup_zulipdev_ssh_keys = f"printf '{ssh_keys_string}' > /home/zulipdev/.ssh/authorized_keys"

    # We pass the hostname as username.zulipdev.org to the DigitalOcean API.
    # But some droplets (eg on 18.04) are created with with hostname set to just username.
    # So we fix the hostname using cloud-init.
    hostname_setup = f"hostnamectl set-hostname {subdomain}.zulipdev.org"

    setup_repo = (
        "cd /home/zulipdev/{1} && "
        "git remote add origin https://github.com/{0}/{1}.git && "
        "git fetch origin && "
        "git clean -f"
    )

    server_repo_setup = setup_repo.format(username, "zulip")
    python_api_repo_setup = setup_repo.format(username, "python-zulip-api")

    erlang_cookie = secrets.token_hex(16)
    setup_erlang_cookie = (
        f"echo '{erlang_cookie}' > /var/lib/rabbitmq/.erlang.cookie && "
        "chown rabbitmq:rabbitmq /var/lib/rabbitmq/.erlang.cookie && "
        "service rabbitmq-server restart"
    )

    cloudconf = f"""\
#!/bin/bash

{setup_zulipdev_ssh_keys}
{setup_root_ssh_keys}
{setup_erlang_cookie}
sed -i "s/PasswordAuthentication yes/PasswordAuthentication no/g" /etc/ssh/sshd_config
service ssh restart
{hostname_setup}
su -c '{server_repo_setup}' zulipdev
su -c '{python_api_repo_setup}' zulipdev
su -c 'git config --global core.editor nano' zulipdev
su -c 'git config --global pull.rebase true' zulipdev
"""
    print("...returning cloud-config data.")
    return cloudconf


def generate_prod_droplet_user_data(username: str, userkey_dicts: List[Dict[str, Any]]) -> str:
    ssh_keys_string = get_ssh_keys_string_from_github_ssh_key_dicts(userkey_dicts)
    setup_root_ssh_keys = f"printf '{ssh_keys_string}' > /root/.ssh/authorized_keys"

    cloudconf = f"""\
#!/bin/bash

{setup_root_ssh_keys}
passwd -d root
sed -i "s/PasswordAuthentication yes/PasswordAuthentication no/g" /etc/ssh/sshd_config
service ssh restart
"""
    print("...returning cloud-config data.")
    return cloudconf


def create_droplet(
    my_token: str,
    template_id: str,
    name: str,
    tags: List[str],
    user_data: str,
    region: str = "nyc3",
) -> Tuple[str, str]:
    droplet = digitalocean.Droplet(
        token=my_token,
        name=name,
        region=region,
        image=template_id,
        size_slug="s-1vcpu-2gb",
        user_data=user_data,
        tags=tags,
        backups=False,
        ipv6=True,
    )

    print("Initiating droplet creation...")
    droplet.create()

    incomplete = True
    while incomplete:
        actions = droplet.get_actions()
        for action in actions:
            action.load()
            print(f"...[{action.type}]: {action.status}")
            if action.type == "create" and action.status == "completed":
                incomplete = False
                break
        if incomplete:
            time.sleep(15)
    print("...droplet created!")
    droplet.load()
    print(f"...ip address for new droplet is: {droplet.ip_address}.")
    return (droplet.ip_address, droplet.ip_v6_address)


def delete_existing_records(records: List[digitalocean.Record], record_name: str) -> None:
    count = 0
    for record in records:
        if (
            record.name == record_name
            and record.domain == "zulipdev.org"
            and record.type in ("AAAA", "A")
        ):
            record.destroy()
            count = count + 1
    if count:
        print(f"Deleted {count} existing A / AAAA records for {record_name}.zulipdev.org.")


def create_dns_record(my_token: str, record_name: str, ipv4: str, ipv6: str) -> None:
    domain = digitalocean.Domain(token=my_token, name="zulipdev.org")
    domain.load()
    records = domain.get_records()

    delete_existing_records(records, record_name)
    wildcard_name = "*." + record_name
    delete_existing_records(records, wildcard_name)

    print(f"Creating new A record for {record_name}.zulipdev.org that points to {ipv4}.")
    domain.create_new_domain_record(type="A", name=record_name, data=ipv4)
    print(f"Creating new A record for *.{record_name}.zulipdev.org that points to {ipv4}.")
    domain.create_new_domain_record(type="A", name=wildcard_name, data=ipv4)

    print(f"Creating new AAAA record for {record_name}.zulipdev.org that points to {ipv6}.")
    domain.create_new_domain_record(type="AAAA", name=record_name, data=ipv6)
    print(f"Creating new AAAA record for *.{record_name}.zulipdev.org that points to {ipv6}.")
    domain.create_new_domain_record(type="AAAA", name=wildcard_name, data=ipv6)


def print_dev_droplet_instructions(username: str, droplet_domain_name: str) -> None:
    print(
        f"""
COMPLETE! Droplet for GitHub user {username} is available at {droplet_domain_name}.

Instructions for use are below. (copy and paste to the user)

------
Your remote Zulip dev server has been created!

- Connect to your server by running
  `ssh zulipdev@{droplet_domain_name}` on the command line
  (Terminal for macOS and Linux, Bash for Git on Windows).
- There is no password; your account is configured to use your SSH keys.
- Once you log in, you should see `(zulip-py3-venv) ~$`.
- To start the dev server, `cd zulip` and then run `./tools/run-dev`.
- While the dev server is running, you can see the Zulip server in your browser at
  http://{droplet_domain_name}:9991.
"""
    )

    print(
        "See [Developing remotely](https://zulip.readthedocs.io/en/latest/development/remote.html) "
        "for tips on using the remote dev instance and "
        "[Git & GitHub guide](https://zulip.readthedocs.io/en/latest/git/index.html) "
        "to learn how to use Git with Zulip.\n"
    )
    print(
        "Note that this droplet will automatically be deleted after a month of inactivity. "
        "If you are leaving Zulip for more than a few weeks, we recommend pushing all of your "
        "active branches to GitHub."
    )
    print("------")


def print_production_droplet_instructions(droplet_domain_name: str) -> None:
    print(
        f"""
-----

Production droplet created successfully!

Connect to the server by running

ssh root@{droplet_domain_name}

-----
"""
    )


def get_zulip_oneclick_app_slug(api_token: str) -> str:
    response = requests.get(
        "https://api.digitalocean.com/v2/1-clicks", headers={"Authorization": f"Bearer {api_token}"}
    ).json()
    one_clicks = response["1_clicks"]

    for one_click in one_clicks:
        if one_click["slug"].startswith("kandralabs"):
            return one_click["slug"]
    raise Exception("Unable to find Zulip One-click app slug")


if __name__ == "__main__":
    args = parser.parse_args()
    username = args.username.lower()
    if args.subdomain:
        subdomain = args.subdomain.lower()
    elif args.production:
        subdomain = "{username}-prod"
    else:
        subdomain = username

    if args.production:
        print(f"Creating production droplet for GitHub user {username}...")
    else:
        print(f"Creating Zulip developer environment for GitHub user {username}...")

    config = get_config()
    api_token = config["digitalocean"]["api_token"]

    assert_github_user_exists(github_username=username)

    public_keys = get_ssh_public_keys_from_github(github_username=username)
    droplet_domain_name = f"{subdomain}.zulipdev.org"

    if args.production:
        template_id = get_zulip_oneclick_app_slug(api_token)
        user_data = generate_prod_droplet_user_data(username=username, userkey_dicts=public_keys)

    else:
        assert_user_forked_zulip_server_repo(username=username)
        user_data = generate_dev_droplet_user_data(
            username=username, subdomain=subdomain, userkey_dicts=public_keys
        )

        # define id of image to create new droplets from; see:
        #     curl -u <API_KEY>: "https://api.digitalocean.com/v2/snapshots | jq .
        template_id = "107085241"

    assert_droplet_does_not_exist(
        my_token=api_token, droplet_name=droplet_domain_name, recreate=args.recreate
    )

    (ipv4, ipv6) = create_droplet(
        my_token=api_token,
        template_id=template_id,
        name=droplet_domain_name,
        tags=[*args.tags, "dev"],
        user_data=user_data,
        region=args.region,
    )

    create_dns_record(my_token=api_token, record_name=subdomain, ipv4=ipv4, ipv6=ipv6)

    if args.production:
        print_production_droplet_instructions(droplet_domain_name=droplet_domain_name)
    else:
        print_dev_droplet_instructions(username=username, droplet_domain_name=droplet_domain_name)

    sys.exit(1)
