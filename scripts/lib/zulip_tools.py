#!/usr/bin/env python3
import argparse
import configparser
import datetime
import functools
import hashlib
import json
import logging
import os
import pwd
import random
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
from typing import IO, Any, Dict, List, Sequence, Set
from urllib.parse import SplitResult

DEPLOYMENTS_DIR = "/home/zulip/deployments"
LOCK_DIR = os.path.join(DEPLOYMENTS_DIR, "lock")
TIMESTAMP_FORMAT = "%Y-%m-%d-%H-%M-%S"

# Color codes
OKBLUE = "\033[94m"
OKGREEN = "\033[92m"
WARNING = "\033[93m"
FAIL = "\033[91m"
ENDC = "\033[0m"
BLACKONYELLOW = "\x1b[0;30;43m"
WHITEONRED = "\x1b[0;37;41m"
BOLDRED = "\x1B[1;31m"
BOLD = "\x1b[1m"
GRAY = "\x1b[90m"

GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"


def overwrite_symlink(src: str, dst: str) -> None:
    dir, base = os.path.split(dst)
    while True:
        # Note: creating a temporary filename like this is not generally
        # secure.  It’s fine in this case because os.symlink refuses to
        # overwrite an existing target; we handle the error and try again.
        tmp = os.path.join(dir, f".{base}.{random.randrange(1 << 40):010x}")
        try:
            os.symlink(src, tmp)
        except FileExistsError:
            continue
        break
    try:
        os.rename(tmp, dst)
    except BaseException:
        os.remove(tmp)
        raise


def parse_cache_script_args(description: str) -> argparse.Namespace:
    # Keep this in sync with clean_unused_caches in provision_inner.py
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument(
        "--threshold",
        dest="threshold_days",
        type=int,
        default=14,
        metavar="<days>",
        help="Any cache which is not in "
        "use by a deployment not older than threshold days(current "
        "installation in dev) and older than threshold days will be "
        "deleted. (defaults to 14)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="If specified then script will only print the caches "
        "that it will delete/keep back. It will not delete any cache.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="If specified then script will print a detailed report "
        "of what is being will deleted/kept back.",
    )
    parser.add_argument(
        "--no-print-headings",
        dest="no_headings",
        action="store_true",
        help="If specified then script will not print headings for "
        "what will be deleted/kept back.",
    )

    args = parser.parse_args()
    args.verbose |= args.dry_run  # Always print a detailed report in case of dry run.
    return args


def get_deploy_root() -> str:
    return os.path.realpath(
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")),
    )


def parse_version_from(deploy_path: str, merge_base: bool = False) -> str:
    if not os.path.exists(os.path.join(deploy_path, "zulip-git-version")):
        try:
            # Pull this tool from _our_ deploy root, since it may not
            # exist historically, but run it the cwd of the old
            # deploy, so we set up its remote.
            subprocess.check_call(
                [os.path.join(get_deploy_root(), "scripts", "lib", "update-git-upstream")],
                cwd=deploy_path,
                preexec_fn=su_to_zulip,
            )
            subprocess.check_call(
                [os.path.join(deploy_path, "tools", "cache-zulip-git-version")],
                cwd=deploy_path,
                preexec_fn=su_to_zulip,
            )
        except subprocess.CalledProcessError:
            pass
    try:
        varname = "ZULIP_MERGE_BASE" if merge_base else "ZULIP_VERSION"
        return subprocess.check_output(
            [sys.executable, "-c", f"from version import {varname}; print({varname})"],
            cwd=deploy_path,
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return "0.0.0"


def get_deployment_version(extract_path: str) -> str:
    version = "0.0.0"
    for item in os.listdir(extract_path):
        item_path = os.path.join(extract_path, item)
        if item.startswith("zulip-server") and os.path.isdir(item_path):
            version = parse_version_from(item_path)
            break
    return version


def is_invalid_upgrade(current_version: str, new_version: str) -> bool:
    if new_version > "1.4.3" and current_version <= "1.3.10":
        return True
    return False


def get_zulip_pwent() -> pwd.struct_passwd:
    deploy_root_uid = os.stat(get_deploy_root()).st_uid
    if deploy_root_uid != 0:
        return pwd.getpwuid(deploy_root_uid)

    # In the case that permissions got messed up and the deployment
    # directory is unexpectedly owned by root, we fallback to the
    # `zulip` user as that's the correct value in production.
    return pwd.getpwnam("zulip")


def get_postgres_pwent() -> pwd.struct_passwd:
    try:
        return pwd.getpwnam("postgres")
    except KeyError:
        return get_zulip_pwent()


def su_to_zulip(save_suid: bool = False) -> None:
    """Warning: su_to_zulip assumes that the zulip checkout is owned by
    the zulip user (or whatever normal user is running the Zulip
    installation).  It should never be run from the installer or other
    production contexts before /home/zulip/deployments/current is
    created."""
    pwent = get_zulip_pwent()
    os.setgid(pwent.pw_gid)
    if save_suid:
        os.setresuid(pwent.pw_uid, pwent.pw_uid, os.getuid())
    else:
        os.setuid(pwent.pw_uid)
    os.environ["HOME"] = pwent.pw_dir


def make_deploy_path() -> str:
    timestamp = datetime.datetime.now().strftime(TIMESTAMP_FORMAT)  # noqa: DTZ005
    return os.path.join(DEPLOYMENTS_DIR, timestamp)


TEMPLATE_DATABASE_DIR = "test-backend/databases"


def get_dev_uuid_var_path(create_if_missing: bool = False) -> str:
    zulip_path = get_deploy_root()
    uuid_path = os.path.join(os.path.realpath(os.path.dirname(zulip_path)), ".zulip-dev-uuid")
    if os.path.exists(uuid_path):
        with open(uuid_path) as f:
            zulip_uuid = f.read().strip()
    else:
        if create_if_missing:
            zulip_uuid = str(uuid.uuid4())
            # We need root access here, since the path will be under /srv/ in the
            # development environment.
            run_as_root(["sh", "-c", 'echo "$1" > "$2"', "-", zulip_uuid, uuid_path])
        else:
            raise AssertionError("Missing UUID file; please run tools/provision!")

    result_path = os.path.join(zulip_path, "var", zulip_uuid)
    os.makedirs(result_path, exist_ok=True)
    return result_path


def get_deployment_lock(error_rerun_script: str) -> None:
    start_time = time.time()
    got_lock = False
    while time.time() - start_time < 300:
        try:
            os.mkdir(LOCK_DIR)
            got_lock = True
            break
        except OSError:
            print(
                WARNING
                + "Another deployment in progress; waiting for lock... "
                + f"(If no deployment is running, rmdir {LOCK_DIR})"
                + ENDC,
                flush=True,
            )
            time.sleep(3)

    if not got_lock:
        print(
            FAIL
            + "Deployment already in progress.  Please run\n"
            + f"  {error_rerun_script}\n"
            + "manually when the previous deployment finishes, or run\n"
            + f"  rmdir {LOCK_DIR}\n"
            + "if the previous deployment crashed."
            + ENDC
        )
        sys.exit(1)


def release_deployment_lock() -> None:
    shutil.rmtree(LOCK_DIR)


def run(args: Sequence[str], **kwargs: Any) -> None:
    # Output what we're doing in the `set -x` style
    print(f"+ {shlex.join(args)}", flush=True)

    try:
        subprocess.check_call(args, **kwargs)
    except subprocess.CalledProcessError as error:
        print()
        if error.returncode < 0:
            try:
                signal_name = signal.Signals(-error.returncode).name
            except ValueError:
                signal_name = f"unknown signal {-error.returncode}"
            print(
                WHITEONRED
                + f"Subcommand of {sys.argv[0]} died with {signal_name}: {shlex.join(args)}"
                + ENDC
            )
        else:
            print(
                WHITEONRED
                + f"Subcommand of {sys.argv[0]} failed with exit status {error.returncode}: {shlex.join(args)}"
                + ENDC
            )
            print(WHITEONRED + "Actual error output for the subcommand is just above this." + ENDC)
        print()
        sys.exit(1)


def log_management_command(cmd: Sequence[str], log_path: str) -> None:
    log_dir = os.path.dirname(log_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    formatter = logging.Formatter("%(asctime)s: %(message)s")
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger = logging.getLogger("zulip.management")
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

    logger.info("Ran %s", shlex.join(cmd))


def get_environment() -> str:
    if os.path.exists(DEPLOYMENTS_DIR):
        return "prod"
    return "dev"


def get_recent_deployments(threshold_days: int) -> Set[str]:
    # Returns a list of deployments not older than threshold days
    # including `/root/zulip` directory if it exists.
    recent = set()
    threshold_date = datetime.datetime.now() - datetime.timedelta(  # noqa: DTZ005
        days=threshold_days
    )
    for dir_name in os.listdir(DEPLOYMENTS_DIR):
        target_dir = os.path.join(DEPLOYMENTS_DIR, dir_name)
        if not os.path.isdir(target_dir):
            # Skip things like uwsgi sockets, symlinks, etc.
            continue
        if not os.path.exists(os.path.join(target_dir, "zerver")):
            # Skip things like "lock" that aren't actually a deployment directory
            continue
        try:
            date = datetime.datetime.strptime(dir_name, TIMESTAMP_FORMAT)  # noqa: DTZ007
            if date >= threshold_date:
                recent.add(target_dir)
        except ValueError:
            # Always include deployments whose name is not in the format of a timestamp.
            recent.add(target_dir)
            # If it is a symlink then include the target as well.
            if os.path.islink(target_dir):
                recent.add(os.path.realpath(target_dir))
    if os.path.exists("/root/zulip"):
        recent.add("/root/zulip")
    return recent


def get_threshold_timestamp(threshold_days: int) -> int:
    # Given number of days, this function returns timestamp corresponding
    # to the time prior to given number of days.
    threshold = datetime.datetime.now() - datetime.timedelta(days=threshold_days)  # noqa: DTZ005
    threshold_timestamp = int(time.mktime(threshold.utctimetuple()))
    return threshold_timestamp


def get_caches_to_be_purged(
    caches_dir: str, caches_in_use: Set[str], threshold_days: int
) -> Set[str]:
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


def purge_unused_caches(
    caches_dir: str,
    caches_in_use: Set[str],
    cache_type: str,
    args: argparse.Namespace,
) -> None:
    if not os.path.exists(caches_dir):
        return

    all_caches = {os.path.join(caches_dir, cache) for cache in os.listdir(caches_dir)}
    caches_to_purge = get_caches_to_be_purged(caches_dir, caches_in_use, args.threshold_days)
    caches_to_keep = all_caches - caches_to_purge

    maybe_perform_purging(
        caches_to_purge, caches_to_keep, cache_type, args.dry_run, args.verbose, args.no_headings
    )
    if args.verbose:
        print("Done!")


def generate_sha1sum_emoji(zulip_path: str) -> str:
    sha = hashlib.sha1()

    filenames = [
        "web/images/zulip-emoji/zulip.png",
        "tools/setup/emoji/emoji_map.json",
        "tools/setup/emoji/build_emoji",
        "tools/setup/emoji/emoji_setup_utils.py",
        "tools/setup/emoji/emoji_names.py",
        "zerver/management/data/unified_reactions.json",
    ]

    for filename in filenames:
        file_path = os.path.join(zulip_path, filename)
        with open(file_path, "rb") as reader:
            sha.update(reader.read())

    # Take into account the version of `emoji-datasource-google` package
    # while generating success stamp.
    with open(os.path.join(zulip_path, "node_modules/emoji-datasource-google/package.json")) as fp:
        emoji_datasource_version = json.load(fp)["version"]
    sha.update(emoji_datasource_version.encode())

    return sha.hexdigest()


def maybe_perform_purging(
    dirs_to_purge: Set[str],
    dirs_to_keep: Set[str],
    dir_type: str,
    dry_run: bool,
    verbose: bool,
    no_headings: bool,
) -> None:
    if dry_run:
        print("Performing a dry run...")
    if not no_headings:
        print(f"Cleaning unused {dir_type}s...")

    for directory in dirs_to_purge:
        if verbose:
            print(f"Cleaning unused {dir_type}: {directory}")
        if not dry_run:
            run_as_root(["rm", "-rf", directory])

    for directory in dirs_to_keep:
        if verbose:
            print(f"Keeping used {dir_type}: {directory}")


@functools.lru_cache(None)
def parse_os_release() -> Dict[str, str]:
    """
    Example of the useful subset of the data:
    {
     'ID': 'ubuntu',
     'VERSION_ID': '18.04',
     'NAME': 'Ubuntu',
     'VERSION': '18.04.3 LTS (Bionic Beaver)',
     'PRETTY_NAME': 'Ubuntu 18.04.3 LTS',
    }

    VERSION_CODENAME (e.g. 'bionic') is nice and readable to Ubuntu
    developers, but we avoid using it, as it is not available on
    RHEL-based platforms.
    """
    distro_info: Dict[str, str] = {}
    with open("/etc/os-release") as fp:
        for line in fp:
            line = line.strip()
            if not line or line.startswith("#"):
                # The line may be blank or a comment, see:
                # https://www.freedesktop.org/software/systemd/man/os-release.html
                continue
            k, v = line.split("=", 1)
            [distro_info[k]] = shlex.split(v)
    return distro_info


@functools.lru_cache(None)
def os_families() -> Set[str]:
    """
    Known families:
    debian (includes: debian, ubuntu)
    ubuntu (includes: ubuntu)
    fedora (includes: fedora, rhel, centos)
    rhel (includes: rhel, centos)
    centos (includes: centos)
    """
    distro_info = parse_os_release()
    return {distro_info["ID"], *distro_info.get("ID_LIKE", "").split()}


def get_tzdata_zi() -> IO[str]:
    if sys.version_info < (3, 9):  # nocoverage
        from backports import zoneinfo
    else:  # nocoverage
        import zoneinfo

    for path in zoneinfo.TZPATH:
        filename = os.path.join(path, "tzdata.zi")
        if os.path.exists(filename):
            return open(filename)  # noqa: SIM115
    raise RuntimeError("Missing time zone data (tzdata.zi)")


def files_and_string_digest(filenames: Sequence[str], extra_strings: Sequence[str]) -> str:
    # see is_digest_obsolete for more context
    sha1sum = hashlib.sha1()
    for fn in filenames:
        with open(fn, "rb") as file_to_hash:
            sha1sum.update(file_to_hash.read())

    for extra_string in extra_strings:
        sha1sum.update(extra_string.encode())

    return sha1sum.hexdigest()


def is_digest_obsolete(
    hash_name: str, filenames: Sequence[str], extra_strings: Sequence[str] = []
) -> bool:
    """
    In order to determine if we need to run some
    process, we calculate a digest of the important
    files and strings whose respective contents
    or values may indicate such a need.

        filenames = files we should hash the contents of
        extra_strings = strings we should hash directly

    Grep for callers to see examples of how this is used.

    To elaborate on extra_strings, they will typically
    be things like:

        - package versions (that we import)
        - settings values (that we stringify with
          json, deterministically)
    """
    last_hash_path = os.path.join(get_dev_uuid_var_path(), hash_name)
    try:
        with open(last_hash_path) as f:
            old_hash = f.read()
    except FileNotFoundError:
        # This is normal for a fresh checkout--a missing
        # digest is an obsolete digest.
        return True

    new_hash = files_and_string_digest(filenames, extra_strings)

    return new_hash != old_hash


def write_new_digest(
    hash_name: str, filenames: Sequence[str], extra_strings: Sequence[str] = []
) -> None:
    hash_path = os.path.join(get_dev_uuid_var_path(), hash_name)
    new_hash = files_and_string_digest(filenames, extra_strings)
    with open(hash_path, "w") as f:
        f.write(new_hash)

    # Be a little verbose here--our callers ensure we
    # only write new digests when things have changed, and
    # making this system more transparent to developers
    # can help them troubleshoot provisioning glitches.
    print("New digest written to: " + hash_path)


def is_root() -> bool:
    if "posix" in os.name and os.geteuid() == 0:
        return True
    return False


def run_as_root(args: List[str], **kwargs: Any) -> None:
    sudo_args = kwargs.pop("sudo_args", [])
    if not is_root():
        args = ["sudo", *sudo_args, "--", *args]
    run(args, **kwargs)


def assert_not_running_as_root() -> None:
    script_name = os.path.abspath(sys.argv[0])
    if is_root():
        pwent = get_zulip_pwent()
        msg = (
            "{shortname} should not be run as root. Use `su {user}` to switch to the 'zulip'\n"
            "user before rerunning this, or use \n  su {user} -c '{name} ...'\n"
            "to switch users and run this as a single command."
        ).format(name=script_name, shortname=os.path.basename(script_name), user=pwent.pw_name)
        print(msg)
        sys.exit(1)


def assert_running_as_root(strip_lib_from_paths: bool = False) -> None:
    script_name = os.path.abspath(sys.argv[0])
    # Since these Python scripts are run inside a thin shell wrapper,
    # we need to replace the paths in order to ensure we instruct
    # users to (re)run the right command.
    if strip_lib_from_paths:
        script_name = script_name.replace("scripts/lib/upgrade", "scripts/upgrade")
    if not is_root():
        print(f"{script_name} must be run as root.")
        sys.exit(1)


def get_config(
    config_file: configparser.RawConfigParser,
    section: str,
    key: str,
    default_value: str = "",
) -> str:
    if config_file.has_option(section, key):
        return config_file.get(section, key)
    return default_value


def get_config_bool(
    config_file: configparser.RawConfigParser, section: str, key: str, default_value: bool = False
) -> bool:
    if config_file.has_option(section, key):
        val = config_file.get(section, key)
        # This list is parallel to puppet/zulip/lib/puppet/parser/functions/zulipconf.rb
        return val in ["1", "y", "t", "true", "yes", "enable", "enabled"]
    return default_value


def get_config_file() -> configparser.RawConfigParser:
    config_file = configparser.RawConfigParser()
    config_file.read("/etc/zulip/zulip.conf")
    return config_file


def get_deploy_options(config_file: configparser.RawConfigParser) -> List[str]:
    return shlex.split(get_config(config_file, "deployment", "deploy_options", ""))


def run_psql_as_postgres(
    config_file: configparser.RawConfigParser,
    sql_query: str,
) -> None:
    dbname = get_config(config_file, "postgresql", "database_name", "zulip")
    subcmd = shlex.join(["psql", "-v", "ON_ERROR_STOP=1", "-d", dbname, "-c", sql_query])
    subprocess.check_call(["su", "postgres", "-c", subcmd])


def get_tornado_ports(config_file: configparser.RawConfigParser) -> List[int]:
    ports = []
    if config_file.has_section("tornado_sharding"):
        ports = sorted(
            {
                int(port)
                for key in config_file.options("tornado_sharding")
                for port in (key[: -len("_regex")] if key.endswith("_regex") else key).split("_")
            }
        )
    if not ports:
        ports = [9800]
    return ports


def get_or_create_dev_uuid_var_path(path: str) -> str:
    absolute_path = f"{get_dev_uuid_var_path()}/{path}"
    os.makedirs(absolute_path, exist_ok=True)
    return absolute_path


def is_vagrant_env_host(path: str) -> bool:
    return ".vagrant" in os.listdir(path)


def has_application_server(once: bool = False) -> bool:
    if once:
        return os.path.exists("/etc/supervisor/conf.d/zulip/zulip-once.conf")
    return (
        # Current path
        os.path.exists("/etc/supervisor/conf.d/zulip/zulip.conf")
        # Old path, relevant for upgrades
        or os.path.exists("/etc/supervisor/conf.d/zulip.conf")
    )


def has_process_fts_updates() -> bool:
    return (
        # Current path
        os.path.exists("/etc/supervisor/conf.d/zulip/zulip_db.conf")
        # Old path, relevant for upgrades
        or os.path.exists("/etc/supervisor/conf.d/zulip_db.conf")
    )


def deport(netloc: str) -> str:
    """Remove the port from a hostname:port string.  Brackets on a literal
    IPv6 address are included."""
    r = SplitResult("", netloc, "", "", "")
    assert r.hostname is not None
    return "[" + r.hostname + "]" if ":" in r.hostname else r.hostname


def start_arg_parser(action: str, add_help: bool = False) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=add_help)
    parser.add_argument("--fill-cache", action="store_true", help="Fill the memcached caches")
    parser.add_argument(
        "--skip-checks", action="store_true", help="Skip syntax and database checks"
    )
    if action == "restart":
        parser.add_argument(
            "--less-graceful",
            action="store_true",
            help="Restart with more concern for expediency than minimizing availability interruption",
        )
        parser.add_argument(
            "--skip-tornado",
            action="store_true",
            help="Do not restart Tornado processes",
        )
    return parser


def listening_publicly(port: int) -> List[str]:
    filter = f"sport = :{port} and not src 127.0.0.1:{port} and not src [::1]:{port}"
    # Parse lines that look like this:
    # tcp    LISTEN     0          128             0.0.0.0:25672        0.0.0.0:*
    lines = (
        subprocess.check_output(
            ["/bin/ss", "-Hnl", filter],
            text=True,
            # Hosts with IPv6 disabled will get "RTNETLINK answers: Invalid
            # argument"; eat stderr to hide that
            stderr=subprocess.DEVNULL,
        )
        .strip()
        .splitlines()
    )
    return [line.split()[4] for line in lines]


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "make_deploy_path":
        print(make_deploy_path())
    elif cmd == "get_dev_uuid":
        print(get_dev_uuid_var_path())
