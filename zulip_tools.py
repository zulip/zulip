#!/usr/bin/env python2.7
from __future__ import print_function
import datetime
import errno
import os
import pwd
import shutil
import subprocess
import sys
import time

DEPLOYMENTS_DIR = "/home/zulip/deployments"
LOCK_DIR = os.path.join(DEPLOYMENTS_DIR, "lock")
TIMESTAMP_FORMAT = '%Y-%m-%d-%H-%M-%S'

# Color codes
OKBLUE = '\033[94m'
OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'

def su_to_zulip():
    pwent = pwd.getpwnam("zulip")
    os.setgid(pwent.pw_gid)
    os.setuid(pwent.pw_uid)

def make_deploy_path():
    timestamp = datetime.datetime.now().strftime(TIMESTAMP_FORMAT)
    return os.path.join(DEPLOYMENTS_DIR, timestamp)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'make_deploy_path':
        print(make_deploy_path())

def mkdir_p(path):
    # Python doesn't have an analog to `mkdir -p` < Python 3.2.
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def get_deployment_lock(error_rerun_script):
    start_time = time.time()
    got_lock = False
    while time.time() - start_time < 300:
        try:
            os.mkdir(LOCK_DIR)
            got_lock = True
            break
        except OSError:
            print(WARNING + "Another deployment in progress; waiting for lock... (If no deployment is running, rmdir %s)" % (LOCK_DIR,) + ENDC)
            sys.stdout.flush()
            time.sleep(3)

    if not got_lock:
        print(FAIL + "Deployment already in progress.  Please run\n"
              + "  %s\n" % (error_rerun_script,)
              + "manually when the previous deployment finishes, or run\n"
              + "  rmdir %s\n"  % (LOCK_DIR,)
              + "if the previous deployment crashed."
              + ENDC)
        sys.exit(1)

def release_deployment_lock():
    shutil.rmtree(LOCK_DIR)

def run(args):
    # Output what we're doing in the `set -x` style
    print("+ %s" % (" ".join(args)))
    process = subprocess.Popen(args)
    rc = process.wait()
    if rc:
        raise subprocess.CalledProcessError(rc, args)
    return 0
