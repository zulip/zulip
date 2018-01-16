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

def get_config():
    # type: () -> configparser.ConfigParser
    config = configparser.ConfigParser()
    config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf.ini'))
    return config

def user_exists(username):
    # type: (str) -> bool
    print("Checking to see if GitHub user {0} exists...".format(username))
    user_api_url = "https://api.github.com/users/{0}".format(username)
    try:
        response = urllib.request.urlopen(user_api_url)
        json.loads(response.read().decode())
        print("...user exists!")
        return True
    except urllib.error.HTTPError as err:
        print(err)
        print("Does the github user {0} exist?".format(username))
        sys.exit(1)

def get_keys(username):
    # type: (str) -> List[Dict[str, Any]]
    print("Checking to see that GitHub user has available public keys...")
    apiurl_keys = "https://api.github.com/users/{0}/keys".format(username)
    try:
        response = urllib.request.urlopen(apiurl_keys)
        userkeys = json.loads(response.read().decode())
        if not userkeys:
            print("No keys found. Has user {0} added ssh keys to their github account?".format(username))
            sys.exit(1)
        print("...public keys found!")
        return userkeys
    except urllib.error.HTTPError as err:
        print(err)
        print("Has user {0} added ssh keys to their github account?".format(username))
        sys.exit(1)

def fork_exists(username):
    # type: (str) -> bool
    print("Checking to see GitHub user has forked zulip/zulip...")
    apiurl_fork = "https://api.github.com/repos/{0}/zulip".format(username)
    try:
        response = urllib.request.urlopen(apiurl_fork)
        json.loads(response.read().decode())
        print("...fork found!")
        return True
    except urllib.error.HTTPError as err:
        print(err)
        print("Has user {0} forked zulip/zulip?".format(username))
        sys.exit(1)

def exit_if_droplet_exists(my_token: str, username: str, recreate: bool) -> None:
    print("Checking to see if droplet for {0} already exists...".format(username))
    manager = digitalocean.Manager(token=my_token)
    my_droplets = manager.get_all_droplets()
    for droplet in my_droplets:
        if droplet.name == "{0}.zulipdev.org".format(username):
            if not recreate:
                print("Droplet for user {0} already exists. Pass --recreate if you "
                      "need to recreate the droplet.".format(username))
                sys.exit(1)
            else:
                print("Deleting existing droplet for {0}.".format(username))
                droplet.destroy()
                return
    print("...No droplet found...proceeding.")

def set_user_data(username, userkeys):
    # type: (str, List[Dict[str, Any]]) -> str
    print("Setting cloud-config data, populated with GitHub user's public keys...")
    ssh_authorized_keys = ""

    # spaces here are important here - these need to be properly indented under
    # ssh_authorized_keys:
    for key in userkeys:
        ssh_authorized_keys += "\n          - {0}".format(key['key'])
    # print(ssh_authorized_keys)

    git_add_remote = "git remote add origin"  # get around "line too long" lint error
    cloudconf = """
    #cloud-config
    users:
      - name: zulipdev
        ssh_authorized_keys:{1}
    runcmd:
      - su -c 'cd /home/zulipdev/zulip && {2} https://github.com/{0}/zulip.git && git fetch origin' zulipdev
      - su -c 'git clean -f' zulipdev
      - su -c 'git config --global core.editor nano' zulipdev
      - su -c 'git config --global pull.rebase true' zulipdev
    power_state:
     mode: reboot
     condition: True
    """.format(username, ssh_authorized_keys, git_add_remote)

    print("...returning cloud-config data.")
    return cloudconf

def create_droplet(my_token, template_id, username, tags, user_data):
    # type: (str, str, str, List[str], str) -> str
    droplet = digitalocean.Droplet(
        token=my_token,
        name='{0}.zulipdev.org'.format(username),
        region='sfo1',
        image=template_id,
        size_slug='2gb',
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
            print("...[{0}]: {1}".format(action.type, action.status))
            if action.type == 'create' and action.status == 'completed':
                incomplete = False
                break
        if incomplete:
            time.sleep(15)
    print("...droplet created!")
    droplet.load()
    print("...ip address for new droplet is: {0}.".format(droplet.ip_address))
    return droplet.ip_address

def delete_existing_records(records: List[digitalocean.Record], record_name: str) -> None:
    count = 0
    for record in records:
        if record.name == record_name and record.domain == 'zulipdev.org' and record.type == 'A':
            record.destroy()
            count = count + 1
    if count:
        print("Deleted {0} existing A records for {1}.zulipdev.org.".format(count, record_name))

def create_dns_record(my_token, username, ip_address):
    # type: (str, str, str) -> None
    domain = digitalocean.Domain(token=my_token, name='zulipdev.org')
    domain.load()
    records = domain.get_records()

    delete_existing_records(records, username)
    wildcard_name = "*." + username
    delete_existing_records(records, wildcard_name)

    print("Creating new A record for {0}.zulipdev.org that points to {1}.".format(username, ip_address))
    domain.create_new_domain_record(type='A', name=username, data=ip_address)
    print("Creating new A record for *.{0}.zulipdev.org that points to {1}.".format(username, ip_address))
    domain.create_new_domain_record(type='A', name=wildcard_name, data=ip_address)

def print_completion(username):
    # type: (str) -> None
    print("""
COMPLETE! Droplet for GitHub user {0} is available at {0}.zulipdev.org.

Instructions for use are below. (copy and paste to the user)

------
Your remote Zulip dev server has been created!

- Connect to your server by running
  `ssh zulipdev@{0}.zulipdev.org` on the command line
  (Terminal for macOS and Linux, Bash for Git on Windows).
- There is no password; your account is configured to use your ssh keys.
- Once you log in, you should see `(zulip-venv) ~$`.
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
    template_id = "29724416"

    # get command line arguments
    args = parser.parse_args()
    print("Creating Zulip developer environment for GitHub user {0}...".format(args.username))

    # get config details
    config = get_config()

    # see if droplet already exists for this user
    user_exists(username=args.username)

    # grab user's public keys
    public_keys = get_keys(username=args.username)

    # now make sure the user has forked zulip/zulip
    fork_exists(username=args.username)

    api_token = config['digitalocean']['api_token']
    # does the droplet already exist?
    exit_if_droplet_exists(my_token=api_token, username=args.username, recreate=args.recreate)

    # set user_data
    user_data = set_user_data(username=args.username, userkeys=public_keys)

    # create droplet
    ip_address = create_droplet(my_token=api_token,
                                template_id=template_id,
                                username=args.username,
                                tags=args.tags,
                                user_data=user_data)

    # create dns entry
    create_dns_record(my_token=api_token, username=args.username, ip_address=ip_address)

    # print completion message
    print_completion(username=args.username)

    sys.exit(1)
