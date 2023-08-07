## Recommended environment setup tutorial

This section guides first-time contributors through installing the
Zulip development environment on Windows, macOS, and Linux.

The recommended method for installing the Zulip development environment is
to use WSL 2 on Windows, and Vagrant with Docker on macOS and Linux.
This method uses the Windows Subsystem for Linux or creates a Linux container
(for macOS and Linux) inside which the Zulip server and all related
services will run.

Contents:

- [Requirements](#requirements)
- [Step 0: Set up Git & GitHub](#step-0-set-up-git--github)
- [Step 1: Install prerequisites](#step-1-install-prerequisites)
- [Step 2: Get Zulip code](#step-2-get-zulip-code)
- [Step 3: Start the development environment](#step-3-start-the-development-environment)
- [Step 4: Developing](#step-4-developing)
- [Troubleshooting and common errors](#troubleshooting-and-common-errors)
- [Specifying an Ubuntu mirror](#specifying-an-ubuntu-mirror)
- [Specifying a proxy](#specifying-a-proxy)
- [Customizing CPU and RAM allocation](#customizing-cpu-and-ram-allocation)

**If you encounter errors installing the Zulip development
environment,** check [troubleshooting and common
errors](#troubleshooting-and-common-errors). If that doesn't help,
please visit [#provision
help](https://chat.zulip.org/#narrow/stream/21-provision-help) in the
[Zulip development community
server](https://zulip.com/development-community/) for real-time help or
[file an issue](https://github.com/zulip/zulip/issues).

When reporting your issue, please include the following information:

- host operating system
- installation method (Vagrant or direct)
- whether or not you are using a proxy
- a copy of Zulip's `vagrant` provisioning logs, available in
  `/var/log/provision.log` on your virtual machine

### Requirements

Installing the Zulip development environment with Vagrant requires
downloading several hundred megabytes of dependencies. You will need
an active internet connection throughout the entire installation
processes. (See [Specifying a proxy](#specifying-a-proxy) if you need
a proxy to access the internet.)

- **All**: 2GB available RAM, Active broadband internet connection,
  [GitHub account](#step-0-set-up-git--github).
- **macOS**: macOS (10.11 El Capitan or newer recommended)
- **Ubuntu LTS**: 20.04 or 22.04
- **Debian**: 11 or 12
- **Fedora**: tested for 36
- **Windows**: Windows 64-bit (Windows 10 recommended), hardware
  virtualization enabled (VT-x or AMD-V), administrator access.

Other Linux distributions work great too, but we don't maintain
documentation for installing Vagrant and Docker on those systems, so
you'll need to find a separate guide and crib from these docs.

### Step 0: Set up Git & GitHub

You can skip this step if you already have Git, GitHub, and SSH access
to GitHub working on your machine.

Follow our [Git guide][set-up-git] in order to install Git, set up a
GitHub account, create an SSH key to access code on GitHub
efficiently, etc. Be sure to create an SSH key and add it to your
GitHub account using
[these instructions](https://help.github.com/en/articles/generating-an-ssh-key).

### Step 1: Install prerequisites

Jump to:

- [macOS](#macos)
- [Ubuntu](#ubuntu)
- [Debian](#debian)
- [Fedora](#fedora)
- [Windows](#windows-10-or-11)

#### macOS

1. Install [Vagrant][vagrant-dl] (latest).
2. Install [Docker Desktop](https://docs.docker.com/desktop/mac/install/) (latest).

Now you are ready for [Step 2: Get Zulip code](#step-2-get-zulip-code).

#### Ubuntu

##### 1. Install Vagrant, Docker, and Git

```console
christie@ubuntu-desktop:~
$ sudo apt install vagrant docker.io git
```

##### 2. Add yourself to the `docker` group:

```console
christie@ubuntu-desktop:~
$ sudo adduser $USER docker
Adding user `christie' to group `docker' ...
Adding user christie to group docker
Done.
```

You will need to reboot for this change to take effect. If it worked,
you will see `docker` in your list of groups:

```console
christie@ubuntu-desktop:~
$ groups | grep docker
christie adm cdrom sudo dip plugdev lpadmin sambashare docker
```

##### 3. Make sure the Docker daemon is running:

If you had previously installed and removed an older version of
Docker, an [Ubuntu
bug](https://bugs.launchpad.net/ubuntu/+source/docker.io/+bug/1844894)
may prevent Docker from being automatically enabled and started after
installation. You can check using the following:

```console
$ systemctl status docker
● docker.service - Docker Application Container Engine
   Loaded: loaded (/lib/systemd/system/docker.service; enabled; vendor preset: enabled)
   Active: active (running) since Mon 2019-07-15 23:20:46 IST; 18min ago
```

If the service is not running, you'll see `Active: inactive (dead)` on
the second line, and will need to enable and start the Docker service
using the following:

```bash
sudo systemctl unmask docker
sudo systemctl enable docker
sudo systemctl start docker
```

Now you are ready for [Step 2: Get Zulip code](#step-2-get-zulip-code).

#### Debian

The setup for Debian is the same as that [for Ubuntu above](#ubuntu).

#### Fedora

The setup for Fedora is mostly equivalent to the [setup for Ubuntu](#ubuntu).
The only difference is the installation of Docker. Fedora does not include the
official `docker-ce` package (named `docker.io` in the
[setup for Ubuntu](#ubuntu)) in their repositories. They provide the package
`moby-engine` which you can choose instead. In case you prefer the official
docker distribution, you can follow
[their documentation to install Docker on Fedora](https://docs.docker.com/engine/install/fedora/).

#### Windows 10 or 11

Zulip's development environment is most easily set up on Windows using
the Windows Subsystem for Linux ([WSL
2](https://docs.microsoft.com/en-us/windows/wsl/wsl2-about))
installation method described here. We require version 0.67.6+ of WSL 2.

1. Enable virtualization through your BIOS settings. This sequence
   depends on your specific hardware and brand, but here are [some
   basic instructions.][windows-bios-virtualization]

1. [Install WSL 2](https://docs.microsoft.com/en-us/windows/wsl/setup/environment).

1. It is required to enable `systemd` for WSL 2 to manage the database, cache and other services.
   To configure it, please follow [this instruction](https://learn.microsoft.com/en-us/windows/wsl/wsl-config#systemd-support).
   Then, you will need to restart WSL 2 before continuing.

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

1. Run the command below to make sure you are inside the WSL disk and not
   in a Windows mounted disk. You will run into permission issues if you
   run `provision` from `zulip` in a Windows mounted disk.

   ```bash
   cd ~  # or cd /home/USERNAME
   ```

1. [Create your fork](../git/cloning.md#step-1a-create-your-fork) of
   the [Zulip server repository](https://github.com/zulip/zulip).

1. [Create a new SSH key][create-ssh-key] for the WSL 2 virtual
   machine and add it to your GitHub account. Note that SSH keys
   linked to your Windows computer will not work within the virtual
   machine.

1. Clone and connect to the Zulip upstream repository:

   ```bash
   git clone --config pull.rebase git@github.com:YOURUSERNAME/zulip.git ~/zulip
   cd zulip
   git remote add -f upstream https://github.com/zulip/zulip.git
   ```

1. Run the following to install the Zulip development environment and
   start it. (If Windows Firewall creates popups to block services,
   simply click **Allow access**.)

   ```bash
   # Install/update the Zulip development environment
   ./tools/provision
   # Enter the Zulip Python environment
   source /srv/zulip-py3-venv/bin/activate
   # Start the development server
   ./tools/run-dev
   ```

1. If you are facing problems or you see error messages after running `./tools/run-dev`,
   you can try running `./tools/provision` again.

1. The [Visual Studio Code Remote -
   WSL](https://code.visualstudio.com/docs/remote/wsl) extension is
   recommended for editing files when developing with WSL. When you
   have it installed, you can run:

   ```bash
   code .
   ```

   to open VS Code connected to your WSL environment.

1. You're done! Now you're ready for [Step 4: Developing](#step-4-developing),
   ignoring the parts about `vagrant` (since you're not using it).

WSL 2 can be uninstalled by following [Microsoft's documentation][uninstall-wsl]

[create-ssh-key]: https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account
[uninstall-wsl]: https://docs.microsoft.com/en-us/windows/wsl/faq#how-do-i-uninstall-a-wsl-distribution-
[windows-bios-virtualization]: https://www.thewindowsclub.com/disable-hardware-virtualization-in-windows-10

### Step 2: Get Zulip code

1. In your browser, visit <https://github.com/zulip/zulip>
   and click the **Fork** button. You will need to be logged in to GitHub to
   do this.
2. Open Terminal (macOS/Linux) or Git BASH (Windows; must
   **run as an Administrator**).
3. In Terminal/Git BASH,
   [clone your fork of the Zulip repository](../git/cloning.md#step-1b-clone-to-your-machine) and
   [connect the Zulip upstream repository](../git/cloning.md#step-1c-connect-your-fork-to-zulip-upstream):

```bash
git clone --config pull.rebase git@github.com:YOURUSERNAME/zulip.git
cd zulip
git remote add -f upstream https://github.com/zulip/zulip.git
```

This will create a `zulip` directory and download the Zulip code into it.

Don't forget to replace `YOURUSERNAME` with your Git username. You will see
something like:

```console
$ git clone --config pull.rebase git@github.com:YOURUSERNAME/zulip.git
Cloning into 'zulip'...
remote: Counting objects: 73571, done.
remote: Compressing objects: 100% (2/2), done.
remote: Total 73571 (delta 1), reused 0 (delta 0), pack-reused 73569
Receiving objects: 100% (73571/73571), 105.30 MiB | 6.46 MiB/s, done.
Resolving deltas: 100% (51448/51448), done.
Checking connectivity... done.
Checking out files: 100% (1912/1912), done.
```

Now you are ready for [Step 3: Start the development
environment](#step-3-start-the-development-environment).

### Step 3: Start the development environment

Change into the zulip directory and tell Vagrant to start the Zulip
development environment with `vagrant up`:

```bash
# On Windows:
cd zulip
vagrant plugin install vagrant-vbguest
vagrant up --provider=virtualbox

# On macOS or Linux:
cd zulip
vagrant up --provider=docker
```

The first time you run this command it will take some time because Vagrant
does the following:

- downloads the base Ubuntu 20.04 virtual machine image (for macOS and Windows)
  or container (for Linux)
- configures this virtual machine/container for use with Zulip,
- creates a shared directory mapping your clone of the Zulip code inside the
  virtual machine/container at `~/zulip`
- runs the `tools/provision` script inside the virtual machine/container, which
  downloads all required dependencies, sets up the python environment for
  the Zulip development server, and initializes a default test
  database. We call this process "provisioning", and it is documented
  in some detail in our [dependencies documentation](../subsystems/dependencies.md).

You will need an active internet connection during the entire
process. (See [Specifying a proxy](#specifying-a-proxy) if you need a
proxy to access the internet.) `vagrant up` can fail while
provisioning if your Internet connection is unreliable. To retry, you
can use `vagrant provision` (`vagrant up` will just boot the guest
without provisioning after the first time). Other common issues are
documented in the
[Troubleshooting and common errors](#troubleshooting-and-common-errors)
section. If that doesn't help, please visit
[#provision help](https://chat.zulip.org/#narrow/stream/21-provision-help)
in the [Zulip development community server](https://zulip.com/development-community/) for
real-time help.

On Windows, you will see the message
`The system cannot find the path specified.` several times. This is
normal and is not a problem.

Once `vagrant up` has completed, connect to the development
environment with `vagrant ssh`:

```console
christie@win10 ~/zulip
$ vagrant ssh
```

You should see output that starts like this:

```console
Welcome to Ubuntu 20.04.4 LTS (GNU/Linux 5.4.0-107-generic x86_64)
```

Congrats, you're now inside the Zulip development environment!

You can confirm this by looking at the command prompt, which starts
with `(zulip-py3-venv)vagrant@`. If it just starts with `vagrant@`, your
provisioning failed and you should look at the
[troubleshooting section](#troubleshooting-and-common-errors).

Next, start the Zulip server:

```console
(zulip-py3-venv) vagrant@vagrant:/srv/zulip
$ ./tools/run-dev
```

You will see several lines of output starting with something like:

```console
2016-05-04 22:20:33,895 INFO: process_fts_updates starting
Recompiling templates
2016-05-04 18:20:34,804 INFO: Not in recovery; listening for FTS updates
done
Validating Django models.py...
System check identified no issues (0 silenced).

Django version 1.8
Tornado server is running at http://localhost:9993/
Quit the server with CTRL-C.
2016-05-04 18:20:40,716 INFO     Tornado loaded 0 event queues in 0.001s
2016-05-04 18:20:40,722 INFO     Tornado  95.5% busy over the past  0.0 seconds
Performing system checks...
```

And ending with something similar to:

```console
http://localhost:9994/webpack-dev-server/
webpack result is served from http://localhost:9991/webpack/
content is served from /srv/zulip

webpack: bundle is now VALID.
2016-05-06 21:43:29,553 INFO     Tornado  31.6% busy over the past 10.6 seconds
2016-05-06 21:43:35,007 INFO     Tornado  23.9% busy over the past 16.0 seconds
```

Now the Zulip server should be running and accessible. Verify this by
navigating to <http://localhost:9991/> in the browser on your main machine.

You should see something like this:

![Image of Zulip development environment](../images/zulip-dev.png)

The Zulip server will continue to run and send output to the terminal window.
When you navigate to Zulip in your browser, check your terminal and you
should see something like:

```console
2016-05-04 18:21:57,547 INFO     127.0.0.1       GET     302 582ms (+start: 417ms) / (unauth@zulip via ?)
[04/May/2016 18:21:57]"GET / HTTP/1.0" 302 0
2016-05-04 18:21:57,568 INFO     127.0.0.1       GET     301   4ms /login (unauth@zulip via ?)
[04/May/2016 18:21:57]"GET /login HTTP/1.0" 301 0
2016-05-04 18:21:57,819 INFO     127.0.0.1       GET     200 209ms (db: 7ms/2q) /login/ (unauth@zulip via ?)
```

Now you're ready for [Step 4: Developing](#step-4-developing).

### Step 4: Developing

#### Where to edit files

You'll work by editing files on your host machine, in the directory where you
cloned Zulip. Use your favorite editor (Sublime, Atom, Vim, Emacs, Notepad++,
etc.).

When you save changes they will be synced automatically to the Zulip
development environment on the virtual machine/container.

Each component of the Zulip development server will automatically
restart itself or reload data appropriately when you make changes. So,
to see your changes, all you usually have to do is reload your
browser. More details on how this works are available below.

Zulip's whitespace rules are all enforced by linters, so be sure to
run `tools/lint` often to make sure you're following our coding style
(or use `tools/setup-git-repo` to run it on just the changed files
automatically whenever you commit).

#### Understanding run-dev debugging output

It's good to have the terminal running `./tools/run-dev` up as you work since error
messages including tracebacks along with every backend request will be printed
there.

See [Logging](../subsystems/logging.md) for further details on the run-dev console
output.

#### Committing and pushing changes with Git

When you're ready to commit or push changes via Git, you will do this by
running Git commands in Terminal (macOS/Linux) or Git BASH (Windows) in the
directory where you cloned Zulip on your main machine.

If you're new to working with Git/GitHub, check out our [Git & GitHub
guide][rtd-git-guide].

#### Maintaining the development environment

If after rebasing onto a new version of the Zulip server, you receive
new errors while starting the Zulip server or running tests, this is
probably not because Zulip's `main` branch is broken. Instead, this
is likely because we've recently merged changes to the development
environment provisioning process that you need to apply to your
development environment. To update your environment, you'll need to
re-provision your Vagrant machine using `vagrant provision` (this just
runs `tools/provision` from your Zulip checkout inside the Vagrant
guest); this should complete in about a minute.

After provisioning, you'll want to
[(re)start the Zulip development server](#step-3-start-the-development-environment).

If you run into any trouble, [#provision
help](https://chat.zulip.org/#narrow/stream/21-provision-help) in the
[Zulip development community
server](https://zulip.com/development-community/) is a great place to ask for
help.

#### Rebuilding the development environment

If you ever want to recreate your development environment again from
scratch (e.g. to test a change you've made to the provisioning
process, or because you think something is broken), you can do so
using `vagrant destroy` and then `vagrant up`. This will usually be
much faster than the original `vagrant up` since the base image is
already cached on your machine (it takes about 5 minutes to run with a
fast Internet connection).

Any additional programs (e.g. Zsh, emacs, etc.) or configuration that
you may have installed in the development environment will be lost
when you recreate it. To address this, you can create a script called
`tools/custom_provision` in your Zulip Git checkout; and place any
extra setup commands there. Vagrant will run `tools/custom_provision`
every time you run `vagrant provision` (or create a Vagrant guest via
`vagrant up`).

#### Shutting down the development environment for use later

To shut down but preserve the development environment so you can use
it again later use `vagrant halt` or `vagrant suspend`.

You can do this from the same Terminal/Git BASH window that is running
run-dev by pressing ^C to halt the server and then typing `exit`. Or you
can halt Vagrant from another Terminal/Git BASH window.

From the window where run-dev is running:

```console
2016-05-04 18:33:13,330 INFO     127.0.0.1       GET     200  92ms /register/ (unauth@zulip via ?)
^C
KeyboardInterrupt
(zulip-py3-venv) vagrant@vagrant:/srv/zulip$ exit
logout
Connection to 127.0.0.1 closed.
christie@win10 ~/zulip
```

Now you can suspend the development environment:

```console
christie@win10 ~/zulip
$ vagrant suspend
==> default: Saving VM state and suspending execution...
```

If `vagrant suspend` doesn't work, try `vagrant halt`:

```console
christie@win10 ~/zulip
$ vagrant halt
==> default: Attempting graceful shutdown of VM...
```

Check out the Vagrant documentation to learn more about
[suspend](https://www.vagrantup.com/docs/cli/suspend.html) and
[halt](https://www.vagrantup.com/docs/cli/halt.html).

#### Resuming the development environment

When you're ready to work on Zulip again, run `vagrant up` (no need to
pass the `--provider` option required above). You will also need to
connect to the virtual machine with `vagrant ssh` and re-start the
Zulip server:

```console
christie@win10 ~/zulip
$ vagrant up
$ vagrant ssh

(zulip-py3-venv) vagrant@vagrant:/srv/zulip
$ ./tools/run-dev
```

### Next steps

Next, read the following to learn more about developing for Zulip:

- [Git & GitHub guide][rtd-git-guide]
- [Using the development environment][rtd-using-dev-env]
- [Testing][rtd-testing] (and [Configuring CI][ci] to
  run the full test suite against any branches you push to your fork,
  which can help you optimize your development workflow).

### Troubleshooting and common errors

Below you'll find a list of common errors and their solutions. Most
issues are resolved by just provisioning again (by running
`./tools/provision` (from `/srv/zulip`) inside the Vagrant guest or
equivalently `vagrant provision` from outside).

If these solutions aren't working for you or you encounter an issue not
documented below, there are a few ways to get further help:

- Ask in [#provision help](https://chat.zulip.org/#narrow/stream/21-provision-help)
  in the [Zulip development community server](https://zulip.com/development-community/).
- [File an issue](https://github.com/zulip/zulip/issues).

When reporting your issue, please include the following information:

- host operating system
- installation method (Vagrant or direct)
- whether or not you are using a proxy
- a copy of Zulip's `vagrant` provisioning logs, available in
  `/var/log/provision.log` on your virtual machine. If you choose to
  post just the error output, please include the **beginning of the
  error output**, not just the last few lines.

The output of `tools/diagnose` run inside the Vagrant guest is also
usually helpful.

#### Vagrant guest doesn't show (zulip-py3-venv) at start of prompt

This is caused by provisioning failing to complete successfully. You
can see the errors in `var/log/provision.log`; it should end with
something like this:

```text
ESC[94mZulip development environment setup succeeded!ESC[0m
```

The `ESC` stuff are the terminal color codes that make it show as a nice
blue in the terminal, which unfortunately looks ugly in the logs.

If you encounter an incomplete `/var/log/provision.log file`, you need to
update your environment. Re-provision your Vagrant machine; if the problem
persists, please come chat with us (see instructions above) for help.

After you provision successfully, you'll need to exit your `vagrant ssh`
shell and run `vagrant ssh` again to get the virtualenv setup properly.

#### Vagrant was unable to mount VirtualBox shared folders

For the following error:

```console
Vagrant was unable to mount VirtualBox shared folders. This is usually
because the filesystem "vboxsf" is not available. This filesystem is
made available via the VirtualBox Guest Additions and kernel
module. Please verify that these guest additions are properly
installed in the guest. This is not a bug in Vagrant and is usually
caused by a faulty Vagrant box. For context, the command attempted
was:

 mount -t vboxsf -o uid=1000,gid=1000 keys /keys
```

If this error starts happening unexpectedly, then just run:

```bash
vagrant halt
vagrant up
```

to reboot the guest. After this, you can do `vagrant provision` and
`vagrant ssh`.

#### ssl read error

If you receive the following error while running `vagrant up`:

```console
SSL read: error:00000000:lib(0):func(0):reason(0), errno 104
```

It means that either your network connection is unstable and/or very
slow. To resolve it, run `vagrant up` until it works (possibly on a
better network connection).

#### Unmet dependencies error

When running `vagrant up` or `provision`, if you see the following error:

```console
==> default: E:unmet dependencies. Try 'apt-get -f install' with no packages (or specify a solution).
```

It means that your local apt repository has been corrupted, which can
usually be resolved by executing the command:

```bash
apt-get -f install
```

#### ssh connection closed by remote host

On running `vagrant ssh`, if you see the following error:

```console
ssh_exchange_identification: Connection closed by remote host
```

It usually means the Vagrant guest is not running, which is usually
solved by rebooting the Vagrant guest via `vagrant halt; vagrant up`. See
[Vagrant was unable to communicate with the guest machine](#vagrant-was-unable-to-communicate-with-the-guest-machine)
for more details.

#### os.symlink error

If you receive the following error while running `vagrant up`:

```console
==> default: Traceback (most recent call last):
==> default: File "./emoji_dump.py", line 75, in <module>
==> default:
==> default: os.symlink('unicode/{}.png'.format(code_point), 'out/{}.png'.format(name))
==> default: OSError
==> default: :
==> default: [Errno 71] Protocol error
```

Then Vagrant was not able to create a symbolic link.

First, if you are using Windows, **make sure you have run Git BASH (or
Cygwin) as an administrator**. By default, only administrators can
create symbolic links on Windows. Additionally [UAC][windows-uac], a
Windows feature intended to limit the impact of malware, can prevent
even administrator accounts from creating symlinks. [Turning off
UAC][disable-uac] will allow you to create symlinks. You can also try
some of the solutions mentioned
[here](https://superuser.com/questions/124679/how-do-i-create-a-link-in-windows-7-home-premium-as-a-regular-user).

[windows-uac]: https://docs.microsoft.com/en-us/windows/security/identity-protection/user-account-control/how-user-account-control-works
[disable-uac]: https://stackoverflow.com/questions/15320550/why-is-secreatesymboliclinkprivilege-ignored-on-windows-8

If you ran Git BASH as administrator but you already had VirtualBox
running, you might still get this error because VirtualBox is not
running as administrator. In that case: close the Zulip VM with
`vagrant halt`; close any other VirtualBox VMs that may be running;
exit VirtualBox; and try again with `vagrant up --provision` from a
Git BASH running as administrator.

Second, VirtualBox does not enable symbolic links by default. Vagrant
starting with version 1.6.0 enables symbolic links for VirtualBox shared
folder.

You can check to see that this is enabled for your virtual machine with
`vboxmanage` command.

Get the name of your virtual machine by running `vboxmanage list vms` and
then print out the custom settings for this virtual machine with
`vboxmanage getextradata YOURVMNAME enumerate`:

```console
christie@win10 ~/zulip
$ vboxmanage list vms
"zulip_default_1462498139595_55484" {5a65199d-8afa-4265-b2f6-6b1f162f157d}

christie@win10 ~/zulip
$ vboxmanage getextradata zulip_default_1462498139595_55484 enumerate
Key: VBoxInternal2/SharedFoldersEnableSymlinksCreate/srv_zulip, Value: 1
Key: supported, Value: false
```

If you see "command not found" when you try to run VBoxManage, you need to
add the VirtualBox directory to your path. On Windows this is mostly likely
`C:\Program Files\Oracle\VirtualBox\`.

If `vboxmanage enumerate` prints nothing, or shows a value of 0 for
VBoxInternal2/SharedFoldersEnableSymlinksCreate/srv_zulip, then enable
symbolic links by running this command in Terminal/Git BASH/Cygwin:

```bash
vboxmanage setextradata YOURVMNAME VBoxInternal2/SharedFoldersEnableSymlinksCreate/srv_zulip 1
```

The virtual machine needs to be shut down when you run this command.

#### Hyper-V error messages

If you get an error message on Windows about lack of Windows Home
support for Hyper-V when running `vagrant up`, the problem is that
Windows is incorrectly attempting to use Hyper-V rather than
Virtualbox as the virtualization provider. You can fix this by
explicitly passing the virtualbox provider to `vagrant up`:

```console
christie@win10 ~/zulip
$ vagrant up --provide=virtualbox
```

#### Connection timeout on `vagrant up`

If you see the following error after running `vagrant up`:

```console
default: SSH address: 127.0.0.1:2222
default: SSH username: vagrant
default: SSH auth method: private key
default: Error: Connection timeout. Retrying...
default: Error: Connection timeout. Retrying...
default: Error: Connection timeout. Retrying...
```

A likely cause is that hardware virtualization is not enabled for your
computer. This must be done via your computer's BIOS settings. Look for a
setting called VT-x (Intel) or (AMD-V).

If this is already enabled in your BIOS, double-check that you are running a
64-bit operating system.

For further information about troubleshooting Vagrant timeout errors [see
this post](https://stackoverflow.com/questions/22575261/vagrant-stuck-connection-timeout-retrying#22575302).

#### Vagrant was unable to communicate with the guest machine

If you see the following error when you run `vagrant up`:

```console
Timed out while waiting for the machine to boot. This means that
Vagrant was unable to communicate with the guest machine within
the configured ("config.vm.boot_timeout" value) time period.

If you look above, you should be able to see the error(s) that
Vagrant had when attempting to connect to the machine. These errors
are usually good hints as to what may be wrong.

If you're using a custom box, make sure that networking is properly
working and you're able to connect to the machine. It is a common
problem that networking isn't setup properly in these boxes.
Verify that authentication configurations are also setup properly,
as well.

If the box appears to be booting properly, you may want to increase
the timeout ("config.vm.boot_timeout") value.
```

This has a range of possible causes, that usually amount to a bug in
Virtualbox or Vagrant. If you see this error, you usually can fix it
by rebooting the guest via `vagrant halt; vagrant up`.

#### Vagrant up fails with subprocess.CalledProcessError

The `vagrant up` command basically does the following:

- Downloads an Ubuntu image and starts it using a Vagrant provider.
- Uses `vagrant ssh` to connect to that Ubuntu guest, and then runs
  `tools/provision`, which has a lot of subcommands that are
  executed via Python's `subprocess` module. These errors mean that
  one of those subcommands failed.

To debug such errors, you can log in to the Vagrant guest machine by
running `vagrant ssh`, which should present you with a standard shell
prompt. You can debug interactively by using e.g.
`cd zulip && ./tools/provision`, and then running the individual
subcommands that failed. Once you've resolved the problem, you can
rerun `tools/provision` to proceed; the provisioning system is
designed to recover well from failures.

The Zulip provisioning system is generally highly reliable; the most common
cause of issues here is a poor network connection (or one where you need a
proxy to access the Internet and haven't [configured the development
environment to use it](#specifying-a-proxy).

Once you've provisioned successfully, you'll get output like this:

```console
Zulip development environment setup succeeded!
(zulip-py3-venv) vagrant@vagrant-base-trusty-amd64:~/zulip$
```

If the `(zulip-py3-venv)` part is missing, this is because your
installation failed the first time before the Zulip virtualenv was
created. You can fix this by just closing the shell and running
`vagrant ssh` again, or using `source /srv/zulip-py3-venv/bin/activate`.

Finally, if you encounter any issues that weren't caused by your
Internet connection, please report them! We try hard to keep Zulip
development environment provisioning free of bugs.

##### `pip install` fails during `vagrant up` on Linux

Likely causes are:

1. Networking issues
2. Insufficient RAM. Check whether you've allotted at least two
   gigabytes of RAM, which is the minimum Zulip
   [requires](#requirements). If
   not, go to your VM settings and increase the RAM, then restart
   the VM.

#### VBoxManage errors related to VT-x or WHvSetupPartition

```console
There was an error while executing `VBoxManage`, a CLI used by Vagrant
for controlling VirtualBox. The command and stderr is shown below.

Command: ["startvm", "8924a681-b4e4-4b7a-96f2-4cb11619f123", "--type", "headless"]

Stderr: VBoxManage.exe: error: (VERR_NEM_MISSING_KERNEL_API).
VBoxManage.exe: error: VT-x is not available (VERR_VMX_NO_VMX)
VBoxManage.exe: error: Details: code E_FAIL (0x80004005), component ConsoleWrap, interface IConsole
```

or

```console
Stderr: VBoxManage.exe: error: Call to WHvSetupPartition failed: ERROR_SUCCESS (Last=0xc000000d/87) (VERR_NEM_VM_CREATE_FAILED)
VBoxManage.exe: error: Details: code E_FAIL (0x80004005), component ConsoleWrap, interface IConsole
```

First, ensure that hardware virtualization support (VT-x or AMD-V) is
enabled in your BIOS.

If the error persists, you may have run into an incompatibility
between VirtualBox and Hyper-V on Windows. To disable Hyper-V, open
command prompt as administrator, run
`bcdedit /set hypervisorlaunchtype off`, and reboot. If you need to
enable it later, run `bcdedit /deletevalue hypervisorlaunchtype`, and
reboot.

#### OSError: [Errno 26] Text file busy

```console
default: Traceback (most recent call last):
…
default:   File "/srv/zulip-py3-venv/lib/python3.6/shutil.py", line 426, in _rmtree_safe_fd
default:     os.rmdir(name, dir_fd=topfd)
default: OSError: [Errno 26] Text file busy: 'baremetrics'
```

This error is caused by a
[bug](https://www.virtualbox.org/ticket/19004) in recent versions of
the VirtualBox Guest Additions for Linux on Windows hosts. You can
check the running version of VirtualBox Guest Additions with this
command:

```bash
vagrant ssh -- 'sudo modinfo -F version vboxsf'
```

The bug has not been fixed upstream as of this writing, but you may be
able to work around it by downgrading VirtualBox Guest Additions to
5.2.44. To do this, create a `~/.zulip-vagrant-config` file and add
this line:

```text
VBOXADD_VERSION 5.2.44
```

Then run these commands (yes, reload is needed twice):

```bash
vagrant plugin install vagrant-vbguest
vagrant reload
vagrant reload --provision
```

### Specifying an Ubuntu mirror

Bringing up a development environment for the first time involves
downloading many packages from the Ubuntu archive. The Ubuntu cloud
images use the global mirror `http://archive.ubuntu.com/ubuntu/` by
default, but you may find that you can speed up the download by using
a local mirror closer to your location. To do this, create
`~/.zulip-vagrant-config` and add a line like this, replacing the URL
as appropriate:

```text
UBUNTU_MIRROR http://us.archive.ubuntu.com/ubuntu/
```

### Specifying a proxy

If you need to use a proxy server to access the Internet, you will
need to specify the proxy settings before running `vagrant up`.
First, install the Vagrant plugin `vagrant-proxyconf`:

```bash
vagrant plugin install vagrant-proxyconf
```

Then create `~/.zulip-vagrant-config` and add the following lines to
it (with the appropriate values in it for your proxy):

```text
HTTP_PROXY http://proxy_host:port
HTTPS_PROXY http://proxy_host:port
NO_PROXY localhost,127.0.0.1,.example.com,.zulipdev.com
```

For proxies that require authentication, the config will be a bit more
complex, e.g.:

```text
HTTP_PROXY http://userName:userPassword@192.168.1.1:8080
HTTPS_PROXY http://userName:userPassword@192.168.1.1:8080
NO_PROXY localhost,127.0.0.1,.example.com,.zulipdev.com
```

You'll want to **double-check** your work for mistakes (a common one
is using `https://` when your proxy expects `http://`). Invalid proxy
configuration can cause confusing/weird exceptions; if you're using a
proxy and get an error, the first thing you should investigate is
whether you entered your proxy configuration correctly.

Now run `vagrant up` in your terminal to install the development
server. If you ran `vagrant up` before and failed, you'll need to run
`vagrant destroy` first to clean up the failed installation.

If you no longer want to use proxy with Vagrant, you can remove the
`HTTP_PROXY` and `HTTPS_PROXY` lines in `~/.zulip-vagrant-config` and
then do a `vagrant reload`.

### Using a different port for Vagrant

You can also change the port on the host machine that Vagrant uses by
adding to your `~/.zulip-vagrant-config` file. E.g. if you set:

```text
HOST_PORT 9971
```

(and `vagrant reload` to apply the new configuration), then you would visit
http://localhost:9971/ to connect to your development server.

If you'd like to be able to connect to your development environment from other
machines than the VM host, you can manually set the host IP address in the
`~/.zulip-vagrant-config` file as well. For example, if you set:

```text
HOST_IP_ADDR 0.0.0.0
```

(and restart the Vagrant guest with `vagrant reload`), your host IP would be
0.0.0.0, a special value for the IP address that means any IP address can
connect to your development server.

### Customizing CPU and RAM allocation

When running Vagrant using a VM-based provider such as VirtualBox or
VMware Fusion, CPU and RAM resources must be explicitly allocated to
the guest system (with Docker and other container-based Vagrant
providers, explicit allocation is unnecessary and the settings
described here are ignored).

Our default Vagrant settings allocate 2 CPUs with 2 GiB of memory for
the guest, which is sufficient to run everything in the development
environment. If your host system has more CPUs, or you have enough
RAM that you'd like to allocate more than 2 GiB to the guest, you can
improve performance of the Zulip development environment by allocating
more resources.

To do so, create a `~/.zulip-vagrant-config` file containing the
following lines:

```text
GUEST_CPUS <number of cpus>
GUEST_MEMORY_MB <system memory (in MB)>
```

For example:

```text
GUEST_CPUS 4
GUEST_MEMORY_MB 8192
```

would result in an allocation of 4 CPUs and 8 GiB of memory to the
guest VM.

After changing the configuration, run `vagrant reload` to reboot the
guest VM with your new configuration.

If at any time you wish to revert back to the default settings, simply
remove the `GUEST_CPUS` and `GUEST_MEMORY_MB` lines from
`~/.zulip-vagrant-config`.

[vagrant-dl]: https://www.vagrantup.com/downloads.html
[install-advanced]: setup-advanced.md
[rtd-git-guide]: ../git/index.md
[rtd-testing]: ../testing/testing.md
[rtd-using-dev-env]: using.md
[rtd-dev-remote]: remote.md
[set-up-git]: ../git/setup.md
[ci]: ../git/cloning.md#step-3-configure-continuous-integration-for-your-fork
