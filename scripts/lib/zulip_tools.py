#!/usr/bin/env python3
from __future__ import print_function
import argparse
import datetime
import errno
import hashlib
import logging
import os
import pwd
import re
import shutil
import subprocess
import sys
import time
import json

if False:
    from typing import Sequence, Set, Text, Any

DEPLOYMENTS_DIR = "/home/zulip/deployments"
LOCK_DIR = os.path.join(DEPLOYMENTS_DIR, "lock")
TIMESTAMP_FORMAT = '%Y-%m-%d-%H-%M-%S'

# Color codes
OKBLUE = '\033[94m'
OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BLACKONYELLOW = '\x1b[0;30;43m'
WHITEONRED = '\x1b[0;37;41m'
BOLDRED = '\x1B[1;31m'

GREEN = '\x1b[32m'
YELLOW = '\x1b[33m'
BLUE = '\x1b[34m'
MAGENTA = '\x1b[35m'
CYAN = '\x1b[36m'

def parse_cache_script_args(description):
    # type: (Text) -> argparse.Namespace
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument(
        "--threshold", dest="threshold_days", type=int, default=14,
        nargs="?", metavar="<days>", help="Any cache which is not in "
        "use by a deployment not older than threshold days(current "
        "installation in dev) and older than threshold days will be "
        "deleted. (defaults to 14)")
    parser.add_argument(
        "--dry-run", dest="dry_run", action="store_true",
        help="If specified then script will only print the caches "
        "that it will delete/keep back. It will not delete any cache.")
    parser.add_argument(
        "--verbose", dest="verbose", action="store_true",
        help="If specified then script will print a detailed report "
        "of what is being will deleted/kept back.")

    args = parser.parse_args()
    args.verbose |= args.dry_run    # Always print a detailed report in case of dry run.
    return args

def get_deployment_version(extract_path):
    # type: (str) -> str
    version = '0.0.0'
    for item in os.listdir(extract_path):
        item_path = os.path.join(extract_path, item)
        if item.startswith('zulip-server') and os.path.isdir(item_path):
            with open(os.path.join(item_path, 'version.py')) as f:
                result = re.search('ZULIP_VERSION = "(.*)"', f.read())
                if result:
                    version = result.groups()[0]
            break
    return version

def is_invalid_upgrade(current_version, new_version):
    # type: (str, str) -> bool
    if new_version > '1.4.3' and current_version <= '1.3.10':
        return True
    return False

def subprocess_text_output(args):
    # type: (Sequence[str]) -> str
    return subprocess.check_output(args, universal_newlines=True).strip()

def su_to_zulip():
    # type: () -> None
    pwent = pwd.getpwnam("zulip")
    os.setgid(pwent.pw_gid)
    os.setuid(pwent.pw_uid)
    os.environ['HOME'] = os.path.abspath(os.path.join(DEPLOYMENTS_DIR, '..'))

def make_deploy_path():
    # type: () -> str
    timestamp = datetime.datetime.now().strftime(TIMESTAMP_FORMAT)
    return os.path.join(DEPLOYMENTS_DIR, timestamp)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'make_deploy_path':
        print(make_deploy_path())

def mkdir_p(path):
    # type: (str) -> None
    # Python doesn't have an analog to `mkdir -p` < Python 3.2.
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def get_deployment_lock(error_rerun_script):
    # type: (str) -> None
    start_time = time.time()
    got_lock = False
    while time.time() - start_time < 300:
        try:
            os.mkdir(LOCK_DIR)
            got_lock = True
            break
        except OSError:
            print(WARNING + "Another deployment in progress; waiting for lock... " +
                  "(If no deployment is running, rmdir %s)" % (LOCK_DIR,) + ENDC)
            sys.stdout.flush()
            time.sleep(3)

    if not got_lock:
        print(FAIL + "Deployment already in progress.  Please run\n" +
              "  %s\n" % (error_rerun_script,) +
              "manually when the previous deployment finishes, or run\n" +
              "  rmdir %s\n"  % (LOCK_DIR,) +
              "if the previous deployment crashed." +
              ENDC)
        sys.exit(1)

def release_deployment_lock():
    # type: () -> None
    shutil.rmtree(LOCK_DIR)

def run(args, **kwargs):
    # type: (Sequence[str], **Any) -> None
    # Output what we're doing in the `set -x` style
    print("+ %s" % (" ".join(args)))

    if kwargs.get('shell'):
        # With shell=True we can only pass string to Popen
        args = " ".join(args)

    try:
        subprocess.check_call(args, **kwargs)
    except subprocess.CalledProcessError:
        print()
        print(WHITEONRED + "Error running a subcommand of %s: %s" % (sys.argv[0], " ".join(args)) +
              ENDC)
        print(WHITEONRED + "Actual error output for the subcommand is just above this." +
              ENDC)
        print()
        raise

def log_management_command(cmd, log_path):
    # type: (Text, Text) -> None
    log_dir = os.path.dirname(log_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    formatter = logging.Formatter("%(asctime)s: %(message)s")
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger = logging.getLogger("zulip.management")
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

    logger.info("Ran '%s'" % (cmd,))

def get_environment():
    # type: () -> Text
    if os.path.exists(DEPLOYMENTS_DIR):
        return "prod"
    if os.environ.get("TRAVIS"):
        return "travis"
    return "dev"

def get_recent_deployments(threshold_days):
    # type: (int) -> Set[Text]
    # Returns a list of deployments not older than threshold days
    # including `/root/zulip` directory if it exists.
    recent = set()
    threshold_date = datetime.datetime.now() - datetime.timedelta(days=threshold_days)
    for dir_name in os.listdir(DEPLOYMENTS_DIR):
        if not os.path.isdir(os.path.join(DEPLOYMENTS_DIR, dir_name)):
            # Skip things like uwsgi sockets, symlinks, etc.
            continue
        if not os.path.exists(os.path.join(DEPLOYMENTS_DIR, dir_name, "zerver")):
            # Skip things like "lock" that aren't actually a deployment directory
            continue
        try:
            date = datetime.datetime.strptime(dir_name, TIMESTAMP_FORMAT)
            if date >= threshold_date:
                recent.add(os.path.join(DEPLOYMENTS_DIR, dir_name))
        except ValueError:
            # Always include deployments whose name is not in the format of a timestamp.
            recent.add(os.path.join(DEPLOYMENTS_DIR, dir_name))
    if os.path.exists("/root/zulip"):
        recent.add("/root/zulip")
    return recent

def get_threshold_timestamp(threshold_days):
    # type: (int) -> int
    # Given number of days, this function returns timestamp corresponding
    # to the time prior to given number of days.
    threshold = datetime.datetime.now() - datetime.timedelta(days=threshold_days)
    threshold_timestamp = int(time.mktime(threshold.utctimetuple()))
    return threshold_timestamp

def get_caches_to_be_purged(caches_dir, caches_in_use, threshold_days):
    # type: (Text, Set[Text], int) -> Set[Text]
    # Given a directory containing caches, a list of caches in use
    # and threshold days, this function return a list of caches
    # which can be purged. Remove the cache only if it is:
    # 1: Not in use by the current installation(in dev as well as in prod).
    # 2: Not in use by a deployment not older than `threshold_days`(in prod).
    # 3: Not in use by '/root/zulip'.
    # 4: Not older than `threshold_days`.
    caches_to_purge = set()
    threshold_timestamp = get_threshold_timestamp(threshold_days)
    for cache_dir_base in os.listdir(caches_dir):
        cache_dir = os.path.join(caches_dir, cache_dir_base)
        if cache_dir in caches_in_use:
            # Never purge a cache which is in use.
            continue
        if os.path.getctime(cache_dir) < threshold_timestamp:
            caches_to_purge.add(cache_dir)
    return caches_to_purge

def purge_unused_caches(caches_dir, caches_in_use, cache_type, args):
    # type: (Text, Set[Text], Text, argparse.Namespace) -> None
    all_caches = set([os.path.join(caches_dir, cache) for cache in os.listdir(caches_dir)])
    caches_to_purge = get_caches_to_be_purged(caches_dir, caches_in_use, args.threshold_days)
    caches_to_keep = all_caches - caches_to_purge

    may_be_perform_purging(
        caches_to_purge, caches_to_keep, cache_type, args.dry_run, args.verbose)
    if args.verbose:
        print("Done!")

def generate_sha1sum_emoji(zulip_path):
    # type: (Text) -> Text
    ZULIP_EMOJI_DIR = os.path.join(zulip_path, 'tools', 'setup', 'emoji')
    sha = hashlib.sha1()

    filenames = ['emoji_map.json', 'build_emoji', 'emoji_setup_utils.py']

    for filename in filenames:
        file_path = os.path.join(ZULIP_EMOJI_DIR, filename)
        with open(file_path, 'rb') as reader:
            sha.update(reader.read())

    # Take into account the version of `emoji-datasource` package while generating success stamp.
    PACKAGE_FILE_PATH = os.path.join(zulip_path, 'package.json')
    with open(PACKAGE_FILE_PATH, 'r') as fp:
        parsed_package_file = json.load(fp)
    dependency_data = parsed_package_file['dependencies']

    if 'emoji-datasource' in dependency_data:
        emoji_datasource_version = dependency_data['emoji-datasource'].encode('utf-8')
    else:
        emoji_datasource_version = b"0"
    sha.update(emoji_datasource_version)

    return sha.hexdigest()

def may_be_perform_purging(dirs_to_purge, dirs_to_keep, dir_type, dry_run, verbose):
    # type: (Set[Text], Set[Text], Text, bool, bool) -> None
    if dry_run:
        print("Performing a dry run...")
    else:
        print("Cleaning unused %ss..." % (dir_type,))

    for directory in dirs_to_purge:
        if verbose:
            print("Cleaning unused %s: %s" % (dir_type, directory))
        if not dry_run:
            subprocess.check_call(["sudo", "rm", "-rf", directory])

    for directory in dirs_to_keep:
        if verbose:
            print("Keeping used %s: %s" % (dir_type, directory))
