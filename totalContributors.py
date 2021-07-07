import os
import pathlib
import subprocess
import sys
from datetime import datetime


def add_log(dict, input):
    for dataset in input:
        name = dataset.split("\t")[1]
        value = int(dataset.split("\t")[0])
        if name in dict:
            dict[name] += value
        else:
            dict[name] = value


def retrieve_log(repo, lower_version, upper_version):
    return subprocess.check_output(
        ["git", "shortlog", "-s", lower_version + ".." + upper_version],
        universal_newlines=True,
        cwd=find_path(repo),
    ).splitlines()


def find_version(time, repo):
    versions_list = subprocess.check_output(
        ["git", "tag", "-l"], universal_newlines=True, cwd=find_path(repo)
    ).splitlines()
    for version in versions_list:
        version_time = subprocess.check_output(
            ["git", "log", "-1", "--format=%ai", version],
            universal_newlines=True,
            cwd=find_path(repo),
        ).split()[0]
        if datetime.strptime(version_time, "%Y-%m-%d") >= datetime.strptime(time, "%Y-%m-%d"):
            return version
    return version


def find_path(repo):
    return os.path.dirname(pathlib.Path().resolve()) + "/" + repo


# extract git version and time
if len(sys.argv) > 1:
    lower_zulip_version = sys.argv[1].split("..")[0]
    upper_zulip_version = sys.argv[1].split("..")[1]
else:
    lower_zulip_version = "1.3.0"  # first Zulip version
    upper_zulip_version = "4.3"  # latest Zulip version

lower_time = subprocess.check_output(
    ["git", "log", "-1", "--format=%ai", lower_zulip_version], universal_newlines=True
).split()[0]
upper_time = subprocess.check_output(
    ["git", "log", "-1", "--format=%ai", upper_zulip_version], universal_newlines=True
).split()[0]

out_dict = {}
zulip = retrieve_log("zulip", lower_zulip_version, upper_zulip_version)
add_log(out_dict, zulip)
for repo_name in [
    "zulip-mobile",
    "zulip-desktop",
    "docker-zulip",
    "python-zulip-api",
    "zulip-terminal",
]:
    lower_repo_version = find_version(lower_time, repo_name)
    upper_repo_version = find_version(upper_time, repo_name)
    repo_log = retrieve_log(repo_name, lower_repo_version, upper_repo_version)
    add_log(out_dict, repo_log)

for keys in out_dict:
    print(str(out_dict[keys]) + "\t" + keys)

print(
    "Total contributions across all Zulip repos within Zulip versions "
    + lower_zulip_version
    + " and "
    + upper_zulip_version
)
