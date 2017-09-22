from __future__ import print_function

import os
import sys
import subprocess
from scripts.lib.zulip_tools import run, ENDC, WARNING
from scripts.lib.hash_reqs import expand_reqs

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENV_CACHE_PATH = "/srv/zulip-venv-cache"

if 'TRAVIS' in os.environ:
    # In Travis CI, we don't have root access
    VENV_CACHE_PATH = "/home/travis/zulip-venv-cache"

if False:
    # Don't add a runtime dependency on typing
    from typing import List, Optional, Tuple, Set

VENV_DEPENDENCIES = [
    "build-essential",
    "libffi-dev",
    "libfreetype6-dev",     # Needed for image types with Pillow
    "libz-dev",             # Needed to handle compressed PNGs with Pillow
    "libjpeg-dev",          # Needed to handle JPEGs with Pillow
    "libldap2-dev",
    "libmemcached-dev",
    "python3-dev",          # Needed to install typed-ast dependency of mypy
    "python-dev",
    "python3-pip",
    "python-pip",
    "python-virtualenv",    # Trusty lacks `python3-virtualenv`.
                            # Fortunately we don't need the library,
                            # only the command, and this suffices.
    "python3-six",
    "python-six",
    "libxml2-dev",          # Used for installing talon
    "libxslt1-dev",         # Used for installing talon
    "libpq-dev",            # Needed by psycopg2
]

def install_venv_deps(requirements_file):
    # type: (str) -> None
    pip_requirements = os.path.join(ZULIP_PATH, "requirements", "pip.txt")
    run(["pip", "install", "-U", "--requirement", pip_requirements])
    run(["pip", "install", "--no-deps", "--requirement", requirements_file])

def get_index_filename(venv_path):
    # type: (str) -> str
    return os.path.join(venv_path, 'package_index')

def get_package_names(requirements_file):
    # type: (str) -> List[str]
    packages = expand_reqs(requirements_file)
    cleaned = []
    operators = ['~=', '==', '!=', '<', '>']
    for package in packages:
        if package.startswith("git+https://") and '#egg=' in package:
            split_package = package.split("#egg=")
            if len(split_package) != 2:
                raise Exception("Unexpected duplicate #egg in package %s" % (package,))
            # Extract the package name from Git requirements entries
            package = split_package[1]

        for operator in operators:
            if operator in package:
                package = package.split(operator)[0]

        package = package.strip()
        if package:
            cleaned.append(package.lower())

    return sorted(cleaned)

def create_requirements_index_file(venv_path, requirements_file):
    # type: (str, str) -> str
    """
    Creates a file, called package_index, in the virtual environment
    directory that contains all the PIP packages installed in the
    virtual environment. This file is used to determine the packages
    that can be copied to a new virtual environment.
    """
    index_filename = get_index_filename(venv_path)
    packages = get_package_names(requirements_file)
    with open(index_filename, 'w') as writer:
        writer.write('\n'.join(packages))
        writer.write('\n')

    return index_filename

def get_venv_packages(venv_path):
    # type: (str) -> Set[str]
    """
    Returns the packages installed in the virtual environment using the
    package index file.
    """
    with open(get_index_filename(venv_path)) as reader:
        return set(p.strip() for p in reader.read().split('\n') if p.strip())

def try_to_copy_venv(venv_path, new_packages):
    # type: (str, Set[str]) -> bool
    """
    Tries to copy packages from an old virtual environment in the cache
    to the new virtual environment. The algorithm works as follows:
        1. Find a virtual environment, v, from the cache that has the
        highest overlap with the new requirements such that:
            a. The new requirements only add to the packages of v.
            b. The new requirements only upgrade packages of v.
        2. Copy the contents of v to the new virtual environment using
        virtualenv-clone.
        3. Delete all .pyc files in the new virtual environment.
    """
    if not os.path.exists(VENV_CACHE_PATH):
        return False

    venv_name = os.path.basename(venv_path)

    overlaps = []  # type: List[Tuple[int, str, Set[str]]]
    old_packages = set()  # type: Set[str]
    for sha1sum in os.listdir(VENV_CACHE_PATH):
        curr_venv_path = os.path.join(VENV_CACHE_PATH, sha1sum, venv_name)
        if (curr_venv_path == venv_path or
                not os.path.exists(get_index_filename(curr_venv_path))):
            continue

        old_packages = get_venv_packages(curr_venv_path)
        # We only consider using using old virtualenvs that only
        # contain packages that we want in our new virtualenv.
        if not (old_packages - new_packages):
            overlap = new_packages & old_packages
            overlaps.append((len(overlap), curr_venv_path, overlap))

    target_log = get_logfile_name(venv_path)
    source_venv_path = None
    if overlaps:
        # Here, we select the old virtualenv with the largest overlap
        overlaps = sorted(overlaps)
        _, source_venv_path, copied_packages = overlaps[-1]
        print('Copying packages from {}'.format(source_venv_path))
        clone_ve = "{}/bin/virtualenv-clone".format(source_venv_path)
        cmd = "sudo {exe} {source} {target}".format(exe=clone_ve,
                                                    source=source_venv_path,
                                                    target=venv_path).split()
        try:
            run(cmd)
        except Exception:
            # Virtualenv-clone is not installed. Install it and try running
            # the command again.
            try:
                run("{}/bin/pip install --no-deps virtualenv-clone".format(
                    source_venv_path).split())
                run(cmd)
            except Exception:
                # virtualenv-clone isn't working, so just make a new venv
                return False

        run(["sudo", "chown", "-R",
             "{}:{}".format(os.getuid(), os.getgid()), venv_path])
        source_log = get_logfile_name(source_venv_path)
        copy_parent_log(source_log, target_log)
        create_log_entry(target_log, source_venv_path, copied_packages,
                         new_packages - copied_packages)
        return True

    return False

def get_logfile_name(venv_path):
    # type: (str) -> str
    return "{}/setup-venv.log".format(venv_path)

def create_log_entry(target_log, parent, copied_packages, new_packages):
    # type: (str, str, Set[str], Set[str]) -> None

    venv_path = os.path.dirname(target_log)
    with open(target_log, 'a') as writer:
        writer.write("{}\n".format(venv_path))
        if copied_packages:
            writer.write(
                "Copied from {}:\n".format(parent))
            writer.write("\n".join('- {}'.format(p) for p in sorted(copied_packages)))
            writer.write("\n")

        writer.write("New packages:\n")
        writer.write("\n".join('- {}'.format(p) for p in sorted(new_packages)))
        writer.write("\n\n")

def copy_parent_log(source_log, target_log):
    # type: (str, str) -> None
    if os.path.exists(source_log):
        run('cp {} {}'.format(source_log, target_log).split())

def do_patch_activate_script(venv_path):
    # type: (str) -> None
    """
    Patches the bin/activate script so that the value of the environment variable VIRTUAL_ENV
    is set to venv_path during the script's execution whenever it is sourced.
    """
    # venv_path should be what we want to have in VIRTUAL_ENV after patching
    script_path = os.path.join(venv_path, "bin", "activate")

    file_obj = open(script_path)
    lines = file_obj.readlines()
    for i, line in enumerate(lines):
        if line.startswith('VIRTUAL_ENV='):
            lines[i] = 'VIRTUAL_ENV="%s"\n' % (venv_path,)
    file_obj.close()

    file_obj = open(script_path, 'w')
    file_obj.write("".join(lines))
    file_obj.close()

def setup_virtualenv(target_venv_path, requirements_file, virtualenv_args=None, patch_activate_script=False):
    # type: (Optional[str], str, Optional[List[str]], bool) -> str

    # Check if a cached version already exists
    path = os.path.join(ZULIP_PATH, 'scripts', 'lib', 'hash_reqs.py')
    output = subprocess.check_output([path, requirements_file], universal_newlines=True)
    sha1sum = output.split()[0]
    if target_venv_path is None:
        cached_venv_path = os.path.join(VENV_CACHE_PATH, sha1sum, 'venv')
    else:
        cached_venv_path = os.path.join(VENV_CACHE_PATH, sha1sum, os.path.basename(target_venv_path))
    success_stamp = os.path.join(cached_venv_path, "success-stamp")
    if not os.path.exists(success_stamp):
        do_setup_virtualenv(cached_venv_path, requirements_file, virtualenv_args or [])
        run(["touch", success_stamp])

    print("Using cached Python venv from %s" % (cached_venv_path,))
    if target_venv_path is not None:
        run(["sudo", "ln", "-nsf", cached_venv_path, target_venv_path])
        if patch_activate_script:
            do_patch_activate_script(target_venv_path)
    activate_this = os.path.join(cached_venv_path, "bin", "activate_this.py")
    exec(open(activate_this).read(), {}, dict(__file__=activate_this))
    return cached_venv_path

def do_setup_virtualenv(venv_path, requirements_file, virtualenv_args):
    # type: (str, str, List[str]) -> None

    # Setup Python virtualenv
    new_packages = set(get_package_names(requirements_file))

    run(["sudo", "rm", "-rf", venv_path])
    if not try_to_copy_venv(venv_path, new_packages):
        # Create new virtualenv.
        run(["sudo", "mkdir", "-p", venv_path])
        run(["sudo", "virtualenv"] + virtualenv_args + [venv_path])
        run(["sudo", "chown", "-R",
             "{}:{}".format(os.getuid(), os.getgid()), venv_path])
        create_log_entry(get_logfile_name(venv_path), "", set(), new_packages)

    create_requirements_index_file(venv_path, requirements_file)
    # Switch current Python context to the virtualenv.
    activate_this = os.path.join(venv_path, "bin", "activate_this.py")
    exec(open(activate_this).read(), {}, dict(__file__=activate_this))

    try:
        install_venv_deps(requirements_file)
    except subprocess.CalledProcessError:
        # Might be a failure due to network connection issues. Retrying...
        print(WARNING + "`pip install` failed; retrying..." + ENDC)
        install_venv_deps(requirements_file)
    run(["sudo", "chmod", "-R", "a+rX", venv_path])
