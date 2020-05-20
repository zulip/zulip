# Creates a Droplet on Digital Ocean for remote Zulip development.
# Particularly useful for sprints/hackathons, interns, and other
# situation where one wants to quickly onboard new contributors.
#
# This script takes one argument: the name of the GitHub user for whom you want
# to create a Zulip developer environment. Requires Python 3.
#
# Requires python-digitalocean library:
# https://github.com/koalalorenzo/python-digitalocean
#
# Also requires Digital Ocean team membership for Zulip and api token:
# https://cloud.digitalocean.com/settings/api/tokens
#
# Copy conf.ini-template to conf.ini and populate with your api token.
#
# usage: python3 create.py <username>

import sys
import configparser
import urllib.error
import urllib.request
import json
import digitalocean
import time
import argparse
import os

from typing import Any, Dict, List

# initiation argument parser
parser = argparse.ArgumentParser(description='Create a Zulip devopment VM Digital Ocean droplet.')
parser.add_argument("username", help="Github username for whom you want to create a Zulip dev droplet")
parser.add_argument('--tags', nargs='+', default=[])
parser.add_argument('-f', '--recreate', dest='recreate', action="store_true", default=False)

def get_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf.ini'))
    return config

def user_exists(username: str) -> bool:
    print("Checking to see if GitHub user {} exists...".format(username))
    user_api_url = "https://api.github.com/users/{}".format(username)
    try:
        response = urllib.request.urlopen(user_api_url)
        json.load(response)
        print("...user exists!")
        return True
    except urllib.error.HTTPError as err:
        print(err)
        print("Does the github user {} exist?".format(username))
        sys.exit(1)

def get_keys(username: str) -> List[Dict[str, Any]]:
    print("Checking to see that GitHub user has available public keys...")
    apiurl_keys = "https://api.github.com/users/{}/keys".format(username)
    try:
        response = urllib.request.urlopen(apiurl_keys)
        userkeys = json.load(response)
        if not userkeys:
            print("No keys found. Has user {} added ssh keys to their github account?".format(username))
            sys.exit(1)
        print("...public keys found!")
        return userkeys
    except urllib.error.HTTPError as err:
        print(err)
        print("Has user {} added ssh keys to their github account?".format(username))
        sys.exit(1)

def fork_exists(username: str) -> bool:
    print("Checking to see GitHub user has forked zulip/zulip...")
    apiurl_fork = "https://api.github.com/repos/{}/zulip".format(username)
    try:
        response = urllib.request.urlopen(apiurl_fork)
        json.load(response)
        print("...fork found!")
        return True
    except urllib.error.HTTPError as err:
        print(err)
        print("Has user {} forked zulip/zulip?".format(username))
        sys.exit(1)

def exit_if_droplet_exists(my_token: str, username: str, recreate: bool) -> None:
    print("Checking to see if droplet for {} already exists...".format(username))
    manager = digitalocean.Manager(token=my_token)
    my_droplets = manager.get_all_droplets()
    for droplet in my_droplets:
        if droplet.name.lower() == "{}.zulipdev.org".format(username):
            if not recreate:
                print("Droplet for user {} already exists. Pass --recreate if you "
                      "need to recreate the droplet.".format(username))
                sys.exit(1)
            else:
                print("Deleting existing droplet for {}.".format(username))
                droplet.destroy()
                return
    print("...No droplet found...proceeding.")

def set_user_data(username: str, userkey_dicts: List[Dict[str, Any]]) -> str:
    print("Setting cloud-config data, populated with GitHub user's public keys...")
    userkeys = [userkey_dict["key"] for userkey_dict in userkey_dicts]
    ssh_keys = "\n".join(userkeys)

    setup_root_ssh_keys = "printf '{keys}' > /root/.ssh/authorized_keys".format(keys=ssh_keys)
    setup_zulipdev_ssh_keys = "printf '{keys}' > /home/zulipdev/.ssh/authorized_keys".format(keys=ssh_keys)

    # We pass the hostname as username.zulipdev.org to the DigitalOcean API.
    # But some droplets (eg on 18.04) are created with with hostname set to just username.
    # So we fix the hostname using cloud-init.
    hostname_setup = "hostnamectl set-hostname {username}.zulipdev.org".format(username=username)

    setup_repo = (
        "cd /home/zulipdev/{1} && "
        "git remote add origin https://github.com/{0}/{1}.git && "
        "git fetch origin && "
        "git clean -f"
    )

    server_repo_setup = setup_repo.format(username, "zulip")
    python_api_repo_setup = setup_repo.format(username, "python-zulip-api")

    cloudconf = """\
#!/bin/bash

{setup_zulipdev_ssh_keys}
{setup_root_ssh_keys}
sed -i "s/PasswordAuthentication yes/PasswordAuthentication no/g" /etc/ssh/sshd_config
service ssh restart
{hostname_setup}
su -c '{server_repo_setup}' zulipdev
su -c '{python_api_repo_setup}' zulipdev
su -c 'git config --global core.editor nano' zulipdev
su -c 'git config --global pull.rebase true' zulipdev
""".format(setup_root_ssh_keys=setup_root_ssh_keys,
           setup_zulipdev_ssh_keys=setup_zulipdev_ssh_keys,
           hostname_setup=hostname_setup,
           server_repo_setup=server_repo_setup, python_api_repo_setup=python_api_repo_setup)
    print("...returning cloud-config data.")
    return cloudconf

def create_droplet(my_token: str, template_id: str, username: str, tags: List[str], user_data: str) -> str:
    droplet = digitalocean.Droplet(
        token=my_token,
        name='{}.zulipdev.org'.format(username),
        region='nyc3',
        image=template_id,
        size_slug='s-1vcpu-2gb',
        user_data=user_data,
        tags=tags,
        backups=False)

    print("Initiating droplet creation...")
    droplet.create()

    incomplete = True
    while incomplete:
        actions = droplet.get_actions()
        for action in actions:
            action.load()
            print("...[{}]: {}".format(action.type, action.status))
            if action.type == 'create' and action.status == 'completed':
                incomplete = False
                break
        if incomplete:
            time.sleep(15)
    print("...droplet created!")
    droplet.load()
    print("...ip address for new droplet is: {}.".format(droplet.ip_address))
    return droplet.ip_address

def delete_existing_records(records: List[digitalocean.Record], record_name: str) -> None:
    count = 0
    for record in records:
        if record.name == record_name and record.domain == 'zulipdev.org' and record.type == 'A':
            record.destroy()
            count = count + 1
    if count:
        print("Deleted {} existing A records for {}.zulipdev.org.".format(count, record_name))

def create_dns_record(my_token: str, username: str, ip_address: str) -> None:
    domain = digitalocean.Domain(token=my_token, name='zulipdev.org')
    domain.load()
    records = domain.get_records()

    delete_existing_records(records, username)
    wildcard_name = "*." + username
    delete_existing_records(records, wildcard_name)

    print("Creating new A record for {}.zulipdev.org that points to {}.".format(username, ip_address))
    domain.create_new_domain_record(type='A', name=username, data=ip_address)
    print("Creating new A record for *.{}.zulipdev.org that points to {}.".format(username, ip_address))
    domain.create_new_domain_record(type='A', name=wildcard_name, data=ip_address)

def print_completion(username: str) -> None:
    print("""
COMPLETE! Droplet for GitHub user {0} is available at {0}.zulipdev.org.

Instructions for use are below. (copy and paste to the user)

------
Your remote Zulip dev server has been created!

- Connect to your server by running
  `ssh zulipdev@{0}.zulipdev.org` on the command line
  (Terminal for macOS and Linux, Bash for Git on Windows).
- There is no password; your account is configured to use your ssh keys.
- Once you log in, you should see `(zulip-py3-venv) ~$`.
- To start the dev server, `cd zulip` and then run `./tools/run-dev.py`.
- While the dev server is running, you can see the Zulip server in your browser at
  http://{0}.zulipdev.org:9991.
""".format(username))

    print("See [Developing remotely](https://zulip.readthedocs.io/en/latest/development/remote.html) "
          "for tips on using the remote dev instance and "
          "[Git & GitHub Guide](https://zulip.readthedocs.io/en/latest/git/index.html) "
          "to learn how to use Git with Zulip.\n")
    print("Note that this droplet will automatically be deleted after a month of inactivity. "
          "If you are leaving Zulip for more than a few weeks, we recommend pushing all of your "
          "active branches to GitHub.")
    print("------")

if __name__ == '__main__':
    # define id of image to create new droplets from
    # You can get this with something like the following. You may need to try other pages.
    # Broken in two to satisfy linter (line too long)
    # curl -X GET -H "Content-Type: application/json" -u <API_KEY>: "https://api.digitaloc
    # ean.com/v2/images?page=5" | grep --color=always base.zulipdev.org
    template_id = "63219191"

    # get command line arguments
    args = parser.parse_args()
    username = args.username.lower()
    print("Creating Zulip developer environment for GitHub user {}...".format(username))

    # get config details
    config = get_config()

    # see if droplet already exists for this user
    user_exists(username=username)

    # grab user's public keys
    public_keys = get_keys(username=username)

    # now make sure the user has forked zulip/zulip
    fork_exists(username=username)

    api_token = config['digitalocean']['api_token']
    # does the droplet already exist?
    exit_if_droplet_exists(my_token=api_token, username=username, recreate=args.recreate)

    # set user_data
    user_data = set_user_data(username=username, userkey_dicts=public_keys)

    # create droplet
    ip_address = create_droplet(my_token=api_token,
                                template_id=template_id,
                                username=username,
                                tags=args.tags,
                                user_data=user_data)

    # create dns entry
    create_dns_record(my_token=api_token, username=username, ip_address=ip_address)

    # print completion message
    print_completion(username=username)

    sys.exit(1)
