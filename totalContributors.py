import subprocess
import pathlib
import os.path
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


def retrieve_log(repo, version):
    return subprocess.check_output(
        ["git", "shortlog", "-s", version], universal_newlines=True, cwd=find_path(repo)
    ).splitlines()


def find_version(time, repo):
    versions_list = subprocess.check_output(
        ["git", "tag", "-l"], universal_newlines=True, cwd=find_path(repo)
    ).splitlines()
    for version in versions_list:
        version_time = subprocess.check_output(
            ["git", "log", "-1", "--format=%ai", version], universal_newlines=True, cwd=find_path(repo)
        ).split()[0]
        if datetime.strptime(version_time, "%Y-%m-%d") >= datetime.strptime(time, "%Y-%m-%d"):
            return version
    return version


def find_path(repo):
    return os.path.dirname(pathlib.Path().resolve()) + "/" + repo


# extract git version and time
if len(sys.argv) > 1:
    zulip_version = sys.argv[1]
else:
    zulip_version = "4.3"

time = subprocess.check_output(
    ["git", "log", "-1", "--format=%ai", zulip_version], universal_newlines=True
).split()[0]

out_dict = {}
zulip = retrieve_log("zulip", zulip_version)
add_log(out_dict, zulip)
for repo_name in [
    "zulip-mobile",
    "zulip-desktop",
    "docker-zulip",
    "python-zulip-api",
    "zulip-terminal",
]:
    repo_version = find_version(time, repo_name)
    repo_log = retrieve_log(repo_name, repo_version)
    add_log(out_dict, repo_log)

for keys in out_dict:
    print(str(out_dict[keys]) + "\t" + keys)

print("Zulip Version " + zulip_version)
