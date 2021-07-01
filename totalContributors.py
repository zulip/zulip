import subprocess
import pathlib
import os.path
import sys
import datetime

def add_log(dict, input):
    for dataset in input:
        name = dataset.split("\t")[1]
        value = int(dataset.split("\t")[0])
        if name in dict:
            dict[name] += value
        else:
            dict[name] = value

def retrieve_log(repo, version):
    return subprocess.run(['git', 'shortlog', '-s', version], capture_output = True, text = True, 
        cwd = os.path.dirname(pathlib.Path().resolve()) + repo).stdout.splitlines()

def find_version(time, repo):
    versions_list = subprocess.run(['git', 'tag', '-l'], capture_output = True, text = True, 
        cwd = os.path.dirname(pathlib.Path().resolve()) + repo).stdout.splitlines()
    for version in versions_list:
        version_time = subprocess.run(['git', 'log', '-1', '--format=%ai', version], capture_output = True, text = True, 
            cwd = os.path.dirname(pathlib.Path().resolve()) + repo).stdout.split()[0]
        if(create_Time_Object(version_time) >= create_Time_Object(time)):
            return version
    return version

def create_Time_Object(time):
    time_arr = time.split("-")
    year = int(time_arr[0])
    month = int(time_arr[1])
    day = int(time_arr[2])
    return datetime.datetime(year, month, day)
    
#extract git version and time
if len(sys.argv) > 1:
    zulip_version = sys.argv[1]
else:
    zulip_version = str(4.3)

time = subprocess.run(['git', 'log', '-1', '--format=%ai', zulip_version], capture_output = True, text = True).stdout.split()[0]

#retrieve versions
zulip_mobile_version = find_version(time, "/zulip-mobile")
zulip_desktop_version = find_version(time, "/zulip-desktop")
docker_zulip_version = find_version(time, "/docker-zulip")
python_zulip_api_version = find_version(time, "/python-zulip-api")
zulip_terminal_version = find_version(time, "/zulip-terminal")
    
#retrieve log data for repo and version    
zulip = retrieve_log("/zulip", zulip_version)
zulip_mobile = retrieve_log("/zulip-mobile", zulip_mobile_version)
zulip_desktop = retrieve_log("/zulip-desktop", zulip_desktop_version)
docker_zulip = retrieve_log("/docker-zulip", docker_zulip_version)
python_zulip_api = retrieve_log("/python-zulip-api", python_zulip_api_version)
zulip_terminal = retrieve_log("/zulip-terminal", zulip_terminal_version)

#initailize empty dictionary
dict = {
}

#add logs
add_log(dict, zulip)
add_log(dict, zulip_mobile)
add_log(dict, zulip_desktop)
add_log(dict, zulip_terminal)
add_log(dict, docker_zulip)
add_log(dict, python_zulip_api)

#print
for keys in dict:
    print(str(dict[keys]) + "\t" + keys)









