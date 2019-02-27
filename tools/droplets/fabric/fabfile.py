 #!/usr/bin/python
# -*- coding: utf-8 -*-

from fabric.api import *
import os

f = open("./packages.txt","r")
APT_PACKAGES = f.read()

env.user = "root"


def clean_up():
    """
    Clean up remote machine before taking snapshot.
    """
    run("rm -rf /tmp/* /var/tmp/*")
    run("history -c")
    run("cat /dev/null > /root/.bash_history")
    run("unset HISTFILE")
    run("apt-get -y autoremove")
    run("apt-get -y autoclean")
    run("find /var/log -mtime -1 -type f -exec truncate -s 0 {} \;")
    run("rm -rf /var/log/*.gz /var/log/*.[0-9] /var/log/*-????????")
    run("rm -rf /var/lib/cloud/instances/*")
    run("rm -rf /var/lib/cloud/instance")
    puts("Removing keys...")
    run("rm -f /root/.ssh/authorized_keys /etc/ssh/*key*")
    run("dd if=/dev/zero of=/zerofile; sync; rm /zerofile; sync")
    run("cat /dev/null > /var/log/lastlog; cat /dev/null > /var/log/wtmp")



def install_files():
    """
    Install files onto remote machine.
    Walk through the files in the "files" directory and copy them to the build system.
    File permissions will be inherited.  If you need to change permissions on uploaded files
    you can do so in a script placed in the "scripts" directory.
    """
    print "--------------------------------------------------"
    print "Copying files in ./files to remote server"
    print "--------------------------------------------------"
    rootDir = './files'
    for dirName, subdirList, fileList in os.walk(rootDir):
        #print('Found directory: %s' % dirName)
        cDir = dirName.replace("./files","")
        print("Entering Directory: %s" % cDir)
        if cDir:
            run("mkdir -p %s" % cDir)
        for fname in fileList:
            cwd = os.getcwd()
            rpath = cDir + "/" + fname
            lpath = cwd + "/files" + cDir + "/" + fname
            print('Moving File: %s' % lpath)
            put(lpath,rpath,mirror_local_mode=True)


    

def install_pkgs():
    """
    Install apt packages listed in APT_PACKAGES
    """
    #Postfix won't install without a prompt without setting some things
    #run("debconf-set-selections <<< \"postfix postfix/main_mailer_type string 'No Configuration'\"")
    #run("debconf-set-selections <<< \"postfix postfix/mailname string localhost.local\"")
    run("DEBIAN_FRONTEND=noninteractive")
    print "--------------------------------------------------"
    print "Installing apt packages in packages.txt"
    print "--------------------------------------------------"
    run("apt-get -qqy update")
    run("apt-get -qqy -o Dpkg::Options::=\"--force-confdef\" -o Dpkg::Options::=\"--force-confold\" upgrade")
    run("apt-get -qqy -o Dpkg::Options::=\"--force-confdef\" -o Dpkg::Options::=\"--force-confold\" install {}".format(APT_PACKAGES))

    # example 3rd paty repo and install certbot
    #run("apt-get -qqy install software-properties-common")
    #run("add-apt-repository ppa:certbot/certbot -y")
    #run("apt-get -qqy update")
    #run("apt-get -qqy install python-certbot-apache")

def run_scripts():
    """
    Run all scripts in the "scripts" directory on the build system
    Scripts are run in alpha-numeric order.  We recommend naming your scripts
    with a name that starts with a two digit number 01-99 to ensure run order.
    """
    print "--------------------------------------------------"
    print "Running scripts in ./scripts"
    print "--------------------------------------------------"
    
    cwd = os.getcwd()
    directory = cwd + "/scripts"

    for f in os.listdir(directory):
        
        lfile = cwd + "/scripts/" + f
        rfile = "/tmp/" + f
        print("Processing script in %s" % lfile)
        put(lfile,rfile)
        run("chmod +x %s" % rfile)
        run(rfile)


@task
def build_image():
    """
    Configure the build droplet, clean up and shut down for snapshotting
    """
    install_pkgs()
    install_files()
    run_scripts()
    clean_up()
    run("exit")
    print "----------------------------------------------------------------"
    print " Build Complete.  Shut down your build droplet from the control"
    print " panel before creating your snapshot."
    print "----------------------------------------------------------------"
    

@task
def build_test():
    """
    Configure the build droplet, but do not clean up or shut down
    """
    install_pkgs()
    install_files()
    run_scripts()
    print "Build complete.  This droplet is NOT ready for use.  Use build_image instead of build_test for your final build"
