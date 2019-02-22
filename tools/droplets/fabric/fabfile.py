#!/usr/bin/env python3

import fabric
from fabric.api import run, put, puts, task, env
import os

env.user = "root"

def clean_up() -> None:
    """
    Clean up remote machine before taking snapshot.
    """
    run("rm -rf /tmp/* /var/tmp/*")
    run("history -c")
    run("cat /dev/null > /root/.bash_history")
    run("unset HISTFILE")
    run("apt-get -y autoremove")
    run("apt-get -y autoclean")
    run(br"find /var/log -mtime -1 -type f -exec truncate -s 0 {} \;")
    run("rm -rf /var/log/*.gz /var/log/*.[0-9] /var/log/*-????????")
    run("rm -rf /var/lib/cloud/instances/*")
    run("rm -rf /var/lib/cloud/instance")
    puts("Removing keys...")
    run("rm -f /root/.ssh/authorized_keys /etc/ssh/*key*")
    run("dd if=/dev/zero of=/zerofile; sync; rm /zerofile; sync")
    run("cat /dev/null > /var/log/lastlog; cat /dev/null > /var/log/wtmp")

def install_files() -> None:
    """
    Install files onto remote machine.
    Walk through the files in the "files" directory and copy them to the build system.
    File permissions will be inherited.  If you need to change permissions on uploaded files
    you can do so in a script placed in the "scripts" directory.
    """
    print("--------------------------------------------------")
    print("Copying files in ./files to remote server")
    print("--------------------------------------------------")
    rootDir = './files'
    for dirName, subdirList, fileList in os.walk(rootDir):
        cDir = dirName.replace("./files", "")
        print("Entering Directory: {}".format(cDir))
        if cDir:
            run("mkdir -p {}".format(cDir))
        for fname in fileList:
            cwd = os.getcwd()
            rpath = cDir + "/" + fname
            lpath = cwd + "/files" + cDir + "/" + fname
            print('Moving File: {}'.format(lpath))
            put(lpath, rpath, mirror_local_mode=True)

def run_scripts() -> None:
    """
    Run all scripts in the "scripts" directory on the build system
    Scripts are run in alpha-numeric order.  We recommend naming your scripts
    with a name that starts with a two digit number 01-99 to ensure run order.
    """
    print("--------------------------------------------------")
    print("Running scripts in ./scripts")
    print("--------------------------------------------------")

    cwd = os.getcwd()
    directory = cwd + "/scripts"

    for f in os.listdir(directory):
        lfile = cwd + "/scripts/" + f
        rfile = "/tmp/" + f
        print("Processing script in {}".format(lfile))
        put(lfile, rfile)
        run("chmod +x {}".format(rfile))
        run(rfile)

def setup_interactive_login_script() -> None:
    run("mkdir /opt/zulip")
    put("interactive_script.sh", "/opt/zulip/interactive_script.sh")
    run("chmod +x /opt/zulip/interactive_script.sh")
    run("cp /root/.bashrc /etc/skel/.zulip_bashrc")
    run("echo '/opt/zulip/interactive_script.sh' >> /root/.bashrc")

@task
def build_image() -> None:
    """
    Configure the build droplet, clean up and shut down for snapshotting
    """
    install_files()
    run_scripts()
    setup_interactive_login_script()
    clean_up()
    run("exit")
    print("----------------------------------------------------------------")
    print(" Build Complete.  Shut down your build droplet from the control")
    print(" panel before creating your snapshot.")
    print("----------------------------------------------------------------")

@task
def build_test() -> None:
    """
    Configure the build droplet, but do not clean up or shut down
    """
    install_files()
    run_scripts()
    setup_interactive_login_script()
    print("Build complete.  This droplet is NOT ready for use.  Use build_image "
          "instead of build_test for your final build")
