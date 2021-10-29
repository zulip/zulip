# Advanced setup

Contents:

- [Installing directly on Ubuntu, Debian, CentOS, or Fedora](#installing-directly-on-ubuntu-debian-centos-or-fedora)
- [Installing directly on Windows 10 with WSL 2](#installing-directly-on-windows-10-with-wsl-2)
- [Using the Vagrant Hyper-V provider on Windows](#using-the-vagrant-hyper-v-provider-on-windows-beta)
- [Newer versions of supported platforms](#newer-versions-of-supported-platforms)

## Installing directly on Ubuntu, Debian, CentOS, or Fedora

If you'd like to install a Zulip development environment on a computer
that's running one of:

- Ubuntu 20.04 Focal, 18.04 Bionic
- Debian 10 Buster, 11 Bullseye (beta)
- CentOS 7 (beta)
- Fedora 33 and 34 (beta)
- RHEL 7 (beta)

You can just run the Zulip provision script on your machine.

**Note**: You should not use the `root` user to run the installation.
If you are using a [remote server](../development/remote.md), see
the
[section on creating appropriate user accounts](../development/remote.html#setting-up-user-accounts).

:::{warning}
There is no supported uninstallation process with this
method. If you want that, use the Vagrant environment, where you can
just do `vagrant destroy` to clean up the development environment.
:::

Start by [cloning your fork of the Zulip repository][zulip-rtd-git-cloning]
and [connecting the Zulip upstream repository][zulip-rtd-git-connect]:

```bash
git clone --config pull.rebase git@github.com:YOURUSERNAME/zulip.git
cd zulip
git remote add -f upstream https://github.com/zulip/zulip.git
```

```bash
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

Zulip's development environment is most easily set up on Windows using
the Windows Subsystem for Linux ([WSL
2](https://docs.microsoft.com/en-us/windows/wsl/wsl2-about))
installation method described here.

1. Enable virtualization through your BIOS settings. This sequence
   depends on your specific hardware and brand, but here are [some
   basic instructions.][windows-bios-virtualization]

1. [Install WSL 2](https://docs.microsoft.com/en-us/windows/wsl/setup/environment).

1. Launch the Ubuntu shell as an administrator and run the following command:

   ```bash
   sudo apt update && sudo apt upgrade
   ```

1. Install dependencies with the following command:

   ```bash
   sudo apt install rabbitmq-server memcached redis-server postgresql
   ```

1. Open `/etc/rabbitmq/rabbitmq-env.conf` using e.g.:

   ```bash
   sudo nano /etc/rabbitmq/rabbitmq-env.conf
   ```

   Confirm the following lines are at the end of your file, and add
   them if not present. Then save your changes (`Ctrl+O`, then `Enter`
   to confirm the path), and exit `nano` (`Ctrl+X`).

   ```ini
   NODE_IP_ADDRESS=127.0.0.1
   NODE_PORT=5672
   ```

1. Run the command below to make sure you are inside the WSL disk and not in a Windows mounted disk.
   You will run into permission issues if you run `provision` from `zulip`
   in a Windows mounted disk.

   ```bash
   cd ~  # or cd /home/USERNAME
   ```

1. [Create your fork](../git/cloning.html#step-1a-create-your-fork) of
   the [Zulip server repository](https://github.com/zulip/zulip).

1. [Create a new SSH key][create-ssh-key] for the WSL-2 Virtual
   Machine and add it to your GitHub account. Note that SSH keys
   linked to your Windows computer will not work within the virtual
   machine.

1. Clone and connect to the Zulip upstream repository:

   ```bash
   git clone --config pull.rebase git@github.com:YOURUSERNAME/zulip.git ~/zulip
   cd zulip
   git remote add -f upstream https://github.com/zulip/zulip.git
   ```

1. Run the following to install the Zulip development environment and
   start it. (If Windows Firewall creates popups to block services, simply click `Allow Access`.)

   ```bash
   # Start database, cache, and other services
   ./tools/wsl/start_services
   # Install/update the Zulip development environment
   ./tools/provision
   # Enter the Zulip Python environment
   source /srv/zulip-py3-venv/bin/activate
   # Start the development server
   ./tools/run-dev.py
   ```

   :::{note}
   If you shut down WSL, after starting it again, you will have to manually start
   the services using `./tools/wsl/start_services`.
   :::

1. If you are facing problems or you see error messages after running `./tools/run-dev.py`,
   you can try running `./tools/provision` again.

1. The [Visual Studio Code Remote -
   WSL](https://code.visualstudio.com/docs/remote/wsl) extension is
   recommended for editing files when developing with WSL. When you
   have it installed, you can run:

   ```bash
   code .
   ```

   to open VSCode connected to your WSL environment.

1. You're done! You can pick up the [documentation on using the
   Zulip development environment](../development/setup-vagrant.html#step-4-developing),
   ignoring the parts about `vagrant` (since you're not using it).

WSL 2 can be uninstalled by following [Microsoft's documentation][uninstall-wsl]

[create-ssh-key]: https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account
[uninstall-wsl]: https://docs.microsoft.com/en-us/windows/wsl/faq#how-do-i-uninstall-a-wsl-distribution-
[windows-bios-virtualization]: https://www.thewindowsclub.com/disable-hardware-virtualization-in-windows-10

## Using the Vagrant Hyper-V provider on Windows (beta)

You should have [Vagrant](https://www.vagrantup.com/downloads) and
[Hyper-V][hyper-v] installed on your system. Ensure they both work as
expected.

[hyper-v]: https://docs.microsoft.com/en-us/virtualization/hyper-v-on-windows/quick-start/enable-hyper-v

**NOTE**: Hyper-V is available only on Windows Enterprise, Pro, or Education.

1. Start by [cloning your fork of the Zulip repository][zulip-rtd-git-cloning]
   and [connecting the Zulip upstream repository][zulip-rtd-git-connect]:

   ```bash
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

   ```console
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

   ```console
   (zulip-py3-venv) vagrant@ubuntu-18:/srv/zulip$ export EXTERNAL_HOST="$(hostname -I | xargs):9991"
   (zulip-py3-venv) vagrant@ubuntu-18:/srv/zulip$ echo $EXTERNAL_HOST
   ```

   The output will be like:

   ```console
   172.28.122.156:9991
   ```

   Make sure you note down this down. This is where your zulip development web
   server can be accessed.

   :::{important}
   The output of the above command changes every time you restart the Vagrant
   development machine. Thus, it will have to be run every time you bring one up.
   This quirk is one reason this method is marked experimental.
   :::

1. You should now be able to start the Zulip development server.

   ```console
   (zulip-py3-venv) vagrant@ubuntu-18:/srv/zulip$ ./tools/run-dev.py
   ```

   The output will look like:

   ```console
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
   the virtual machine. You can generally work around this error by
   closing all other running programs and running
   `vagrant up --provider=hyperv` again. You can reopen the other
   programs after the provisioning is completed. If it still isn't
   enough, try restarting your system and running the command again.

2. Be patient the first time you run `./tools/run-dev.py`.

As with other installation methods, please visit [#provision
help][provision-help] in the [Zulip development community
server](https://zulip.com/developer-community/) if you need help.

[provision-help]: https://chat.zulip.org/#narrow/stream/21-provision-help

## Newer versions of supported platforms

You can use
[our provisioning tool](#installing-directly-on-ubuntu-debian-centos-or-fedora)
to set up the Zulip development environment on current versions of
these platforms reliably and easily, so we no longer maintain manual
installation instructions for these platforms.

If `tools/provision` doesn't yet support a newer release of Debian or
Ubuntu that you're using, we'd love to add support for it. It's
likely only a few lines of changes to `tools/lib/provision.py` and
`scripts/lib/setup-apt-repo` if you'd like to do it yourself and
submit a pull request, or you can ask for help in
[#development help](https://chat.zulip.org/#narrow/stream/49-development-help)
on chat.zulip.org, and a core team member can help guide you through
adding support for the platform.
