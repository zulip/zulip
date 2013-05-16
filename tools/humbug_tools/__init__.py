import subprocess
import os

# check_output is backported from subprocess.py in Python 2.7

def check_output(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise subprocess.CalledProcessError(retcode, cmd, output=output)
    return output

DEPLOYMENTS_DIR = "/home/humbug/humbug-deployments"
LOCK_DIR = os.path.join(DEPLOYMENTS_DIR, "lock")
TIMESTAMP_FORMAT = '%Y-%m-%d-%H-%M-%S'
