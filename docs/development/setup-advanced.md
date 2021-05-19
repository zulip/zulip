# Advanced setup

Contents:

* [Installing directly on Ubuntu, Debian, CentOS, or Fedora](#installing-directly-on-ubuntu-debian-centos-or-fedora)
* [Installing directly on Windows 10 with WSL 2](#installing-directly-on-windows-10-with-wsl-2)
* [Using the Vagrant Hyper-V provider on Windows](#using-the-vagrant-hyper-v-provider-on-windows-beta)
* [Newer versions of supported platforms](#newer-versions-of-supported-platforms)
* [Installing directly on cloud9](#installing-on-cloud9)

## Installing directly on Ubuntu, Debian, CentOS, or Fedora

If you'd like to install a Zulip development environment on a computer
that's running one of:

* Ubuntu 20.04 Focal, 18.04 Bionic
* Debian 10 Buster, 11 Bullseye (beta)
* CentOS 7 (beta)
* Fedora 33 (beta)
* RHEL 7 (beta)

You can just run the Zulip provision script on your machine.

**Note**: You should not use the `root` user to run the installation.
If you are using a [remote server](../development/remote.md), see
the
[section on creating appropriate user accounts](../development/remote.html#setting-up-user-accounts).

```eval_rst
.. warning::
    There is no supported uninstallation process with this
    method.  If you want that, use the Vagrant environment, where you can
    just do `vagrant destroy` to clean up the development environment.
```

Start by [cloning your fork of the Zulip repository][zulip-rtd-git-cloning]
and [connecting the Zulip upstream repository][zulip-rtd-git-connect]:

```
git clone --config pull.rebase git@github.com:YOURUSERNAME/zulip.git
cd zulip
git remote add -f upstream https://github.com/zulip/zulip.git
```

```
# On CentOS/RHEL, you must first install epel-release, and then python36,
# and finally you must run `sudo ln -nsf /usr/bin/python36 /usr/bin/python3`
# On Fedora, you must first install python3
# From a clone of zulip.git
./tools/provision
source /srv/zulip-py3-venv/bin/activate
./tools/run-dev.py  # starts the development server
```

Once you've done the above setup, you can pick up the [documentation
on using the Zulip development
environment](../development/setup-vagrant.html#step-4-developing),
ignoring the parts about `vagrant` (since you're not using it).

## Installing directly on Windows 10 with WSL 2

We will be using Microsoft's new feature <a href="https://docs.microsoft.com/en-us/windows/wsl/wsl2-about" target="_blank">WSL 2</a> for
installation.

WSL 2 can be uninstalled by following the instructions [here from Microsoft](https://docs.microsoft.com/en-us/windows/wsl/faq#how-do-i-uninstall-a-wsl-distribution-).

Zulip's development environment is most easily set up on Windows using
the [WSL 2](https://docs.microsoft.com/en-us/windows/wsl/wsl2-about)
installation method described here.


1. Install WSL 2 by following the instructions provided by Microsoft
[here](https://docs.microsoft.com/en-us/windows/wsl/wsl2-install).

1. Install the `Ubuntu 18.04` Linux distribution from the Microsoft
   Store.

1. Launch the `Ubuntu 18.04` shell and run the following commands:

   ```
   sudo apt update && sudo apt upgrade
   sudo apt install rabbitmq-server memcached redis-server postgresql
   ```

1. Open `/etc/rabbitmq/rabbitmq-env.conf` using e.g.:

   ```
   sudo vim /etc/rabbitmq/rabbitmq-env.conf
   ```

   Add the following lines at the end of your file and save:

   ```
   NODE_IP_ADDRESS=127.0.0.1
   NODE_PORT=5672
   ```

1. Make sure you are inside the WSL disk and not in a Windows mounted disk.
   You will run into permission issues if you run `provision` from `zulip`
   in a Windows mounted disk.
   ```
   cd ~  # or cd /home/USERNAME
   ```

1. [Clone your fork of the Zulip repository][zulip-rtd-git-cloning]
   and [connecting the Zulip upstream repository][zulip-rtd-git-connect]:

   ```
   git clone --config pull.rebase git@github.com:YOURUSERNAME/zulip.git ~/zulip
   cd zulip
   git remote add -f upstream https://github.com/zulip/zulip.git
   ```

1. Run the following to install the Zulip development environment and
   start it (click `Allow access` if you get popups for Windows Firewall
   blocking some services)

   ```
   # Start database, cache, and other services
   ./tools/wsl/start_services
   # Install/update the Zulip development environment
   ./tools/provision
   # Enter the Zulip Python environment
   source /srv/zulip-py3-venv/bin/activate
   # Start the development server
   ./tools/run-dev.py
   ```

   ```eval_rst
   .. note::
       If you shut down WSL, after starting it again, you will have to manually start
       the services using ``./tools/wsl/start_services``.
   ```

1. If you are facing problems or you see error messages after running `./tools/run-dev.py`,
   you can try running `./tools/provision` again.

1. [Visual Studio Code Remote - WSL](https://code.visualstudio.com/docs/remote/wsl) is
   recommended for editing files when developing with WSL.

1. You're done!  You can pick up the [documentation on using the
   Zulip development
   environment](../development/setup-vagrant.html#step-4-developing),
   ignoring the parts about `vagrant` (since you're not using it).

WSL 2 can be uninstalled by following [Microsoft's documentation][uninstall-wsl]

[uninstall-wsl]: https://docs.microsoft.com/en-us/windows/wsl/faq#how-do-i-uninstall-a-wsl-distribution-

## Using the Vagrant Hyper-V provider on Windows (beta)

You should have [Vagrant](https://www.vagrantup.com/downloads) and
[Hyper-V][hyper-v] installed on your system. Ensure they both work as
expected.

[hyper-v]: https://docs.microsoft.com/en-us/virtualization/hyper-v-on-windows/quick-start/enable-hyper-v

**NOTE**: Hyper-V is available only on Windows Enterprise, Pro, or Education.

1. Start by [cloning your fork of the Zulip repository][zulip-rtd-git-cloning]
   and [connecting the Zulip upstream repository][zulip-rtd-git-connect]:

   ```
   git clone --config pull.rebase git@github.com:YOURUSERNAME/zulip.git
   cd zulip
   git remote add -f upstream https://github.com/zulip/zulip.git
   ```

1. You will have to open up powershell with administrator rights in
   order to use Hyper-V. Then provision the development environment:

   ```bash
   vagrant up --provider=hyperv
   ```

   You should get output like this:

   ```text
   Bringing machine 'default' up with 'hyperv' provider...
   ==> default: Verifying Hyper-V is enabled...
   ==> default: Verifying Hyper-V is accessible...
   <other stuff>...
   ==> default: Waiting for the machine to report its IP address...
       default: Timeout: 120 seconds
       default: IP: 172.28.119.70
   ==> default: Waiting for machine to boot. This may take a few minutes...
       default: SSH address: 172.28.122.156
   ==> default: Machine booted and ready!
   ==> default: Preparing SMB shared folders...
   Vagrant requires administrator access for pruning SMB shares and
   may request access to complete removal of stale shares.
   ==> default: Starting the machine...
   <other stuff>...
    default: Username (user[@domain]): <your-machine-username>
    default: Password (will be hidden):
   ```

   At this point, you will be prompted for your Windows administrator
   username and password (not your Microsoft account credentials).

1. SSH into your newly created virtual machine

   ```bash
   vagrant ssh
   ```

   This will ssh you into the bash shell of the Zulip development environment
   where you can execute bash commands.

1. Set the `EXTERNAL_HOST` environment variable.

   ```bash
   (zulip-py3-venv) vagrant@ubuntu-18:/srv/zulip$ export EXTERNAL_HOST="$(hostname -I | xargs):9991"
   (zulip-py3-venv) vagrant@ubuntu-18:/srv/zulip$ echo $EXTERNAL_HOST
   ```

   The output will be like:

   ```text
   172.28.122.156:9991
   ```

   Make sure you note down this down. This is where your zulip development web
   server can be accessed.

   ```eval_rst
   .. important::
      The output of the above command changes every time you restart the Vagrant
      development machine. Thus, it will have to be run every time you bring one up.
      This quirk is one reason this method is marked experimental.
   ```

1. You should now be able to start the Zulip development server.

   ```bash
   (zulip-py3-venv) vagrant@ubuntu-18:/srv/zulip$ ./tools/run-dev.py
   ```

   The output will look like:

   ```text
   Starting Zulip on:

        http://172.30.24.235:9991/

   Internal ports:
      9991: Development server proxy (connect here)
      9992: Django
      9993: Tornado
      9994: webpack
   ```

   Visit the indicated URL in your web browser.

1. You can stop the development environment using `vagrant halt`, and restart it
   using `vagrant up` and then going through steps **3** and **4** again.

### Problems you may encounter

1. If you get the error `Hyper-V could not initialize memory`, this is
   likely because your system has insufficient free memory to start
   the virtual machine.  You can generally work around this error by
   closing all other running programs and running `vagrant up
   --provider=hyperv` again. You can reopen the other programs after
   the provisioning is completed. If it still isn't enough, try
   restarting your system and running the command again.

2. Be patient the first time you run `./tools/run-dev.py`.

As with other installation methods, please visit [#provision
help][provision-help] in the [Zulip development community
server](../contributing/chat-zulip-org.md) if you need help.

[provision-help]: https://chat.zulip.org/#narrow/stream/21-provision-help

## Newer versions of supported platforms

You can use
[our provisioning tool](#installing-directly-on-ubuntu-debian-centos-or-fedora)
to set up the Zulip development environment on current versions of
these platforms reliably and easily, so we no longer maintain manual
installation instructions for these platforms.

If `tools/provision` doesn't yet support a newer release of Debian or
Ubuntu that you're using, we'd love to add support for it.  It's
likely only a few lines of changes to `tools/lib/provision.py` and
`scripts/lib/setup-apt-repo` if you'd like to do it yourself and
submit a pull request, or you can ask for help in
[#development help](https://chat.zulip.org/#narrow/stream/49-development-help)
on chat.zulip.org, and a core team member can help guide you through
adding support for the platform.

## Installing on Cloud9

AWS Cloud9 is a cloud-based integrated development environment (IDE)
that lets you write, run, and debug your code with just a browser. It
includes a code editor, debugger, and terminal.

This section documents how to set up the Zulip development environment
in a Cloud9 workspace.  If you don't have an existing Cloud9 account,
you can sign up [here](https://aws.amazon.com/cloud9/).

* Create a Workspace, and select the blank template.
* Resize the workspace to be 1GB of memory and 4GB of disk
  space. (This is under free limit for both the old Cloud9 and the AWS
  Free Tier).
* Clone the zulip repo: `git clone --config pull.rebase
  https://github.com/<your-username>/zulip.git`
* Restart rabbitmq-server since its broken on Cloud9: `sudo service
  rabbitmq-server restart`.
* And run provision `cd zulip && ./tools/provision`, once this is done.
* Activate the Zulip virtual environment by `source
  /srv/zulip-py3-venv/bin/activate` or by opening a new terminal.

#### Install zulip-cloud9

There's a NPM package, `zulip-cloud9`, that provides a wrapper around
the Zulip development server for use in the Cloud9 environment.

Note: `npm i -g zulip-cloud9` does not work in zulip's virtual
environment.  Although by default, any packages installed in workspace
folder (i.e. the top level folder) are added to `$PATH`.

```bash
cd .. # switch to workspace folder if you are in zulip directory
npm i zulip-cloud9
zulip-dev start # to start the development server
```

If you get error of the form `bash: cannot find command zulip-dev`,
you need to start a new terminal.

Your development server would be running at
`https://<workspace-name>-<username>.c9users.io` on port 8080.  You
dont need to add `:8080` to your URL, since the Cloud9 proxy should
automatically forward the connection. You might want to visit
[zulip-cloud9 repo](https://github.com/cPhost/zulip-cloud9) and it's
[wiki](https://github.com/cPhost/zulip-cloud9/wiki) for more info on
how to use zulip-cloud9 package.

[zulip-rtd-git-cloning]: ../git/cloning.html#step-1b-clone-to-your-machine
[zulip-rtd-git-connect]: ../git/cloning.html#step-1c-connect-your-fork-to-zulip-upstream
[port-forward-setup]: ../development/remote.html#running-the-development-server
