## Vagrant environment setup tutorial

This section guides first-time contributors through installing the
Zulip development environment on Windows, macOS, Ubuntu and Debian.

The recommended method for installing the Zulip development environment is to use
Vagrant with VirtualBox on Windows and macOS, and Vagrant with Docker on
Ubuntu. This method creates a virtual machine (for Windows and macOS)
or a Linux container (for Ubuntu) inside which the Zulip server and
all related services will run.

Contents:
* [Requirements](#requirements)
* [Step 0: Set up Git & GitHub](#step-0-set-up-git-github)
* [Step 1: Install prerequisites](#step-1-install-prerequisites)
* [Step 2: Get Zulip code](#step-2-get-zulip-code)
* [Step 3: Start the development environment](#step-3-start-the-development-environment)
* [Step 4: Developing](#step-4-developing)
* [Troubleshooting and common errors](#troubleshooting-and-common-errors)
* [Specifying an Ubuntu mirror](#specifying-an-ubuntu-mirror)
* [Specifying a proxy](#specifying-a-proxy)
* [Customizing CPU and RAM allocation](#customizing-cpu-and-ram-allocation)

**If you encounter errors installing the Zulip development
environment,** check [troubleshooting and common
errors](#troubleshooting-and-common-errors). If that doesn't help,
please visit [#provision
help](https://chat.zulip.org/#narrow/stream/21-provision-help) in the
[Zulip development community
server](../contributing/chat-zulip-org.md) for real-time help or
[file an issue](https://github.com/zulip/zulip/issues).

When reporting your issue, please include the following information:

* host operating system
* installation method (Vagrant or direct)
* whether or not you are using a proxy
* a copy of Zulip's `vagrant` provisioning logs, available in
  `/var/log/provision.log` on your virtual machine

### Requirements

Installing the Zulip development environment with Vagrant requires
downloading several hundred megabytes of dependencies. You will need
an active internet connection throughout the entire installation
processes. (See [Specifying a proxy](#specifying-a-proxy) if you need
a proxy to access the internet.)

- **All**: 2GB available RAM, Active broadband internet connection, [GitHub account][set-up-git].
- **macOS**: macOS (10.11 El Capitan or newer recommended)
- **Ubuntu LTS**: 20.04 or 18.04
  - or **Debian**: 10 "buster"
- **Windows**: Windows 64-bit (Win 10 recommended), hardware
  virtualization enabled (VT-x or AMD-V), administrator access.

Other Linux distributions work great too, but we don't maintain
documentation for installing Vagrant and Docker on those systems, so
you'll need to find a separate guide and crib from the Debian/Ubuntu
docs.

### Step 0: Set up Git & GitHub

You can skip this step if you already have Git, GitHub, and SSH access
to GitHub working on your machine.

Follow our [Git guide][set-up-git] in order to install Git, set up a
GitHub account, create an SSH key to access code on GitHub
efficiently, etc.  Be sure to create an SSH key and add it to your
GitHub account using
[these instructions](https://help.github.com/en/articles/generating-an-ssh-key).

### Step 1: Install prerequisites

Jump to:

* [macOS](#macos)
* [Ubuntu](#ubuntu)
* [Debian](#debian)
* [Windows](#windows-10)

#### macOS

1. Install [Vagrant][vagrant-dl] (latest).
2. Install [VirtualBox][vbox-dl] (latest).

(For a non-free option, but better performance, you can also use [VMware
Fusion][vmware-fusion-dl] with the [VMware Fusion Vagrant
plugin][vagrant-vmware-fusion-dl] or [Parallels Desktop][parallels-desktop-dl] as
a provider for Vagrant.)

Now you are ready for [Step 2: Get Zulip code](#step-2-get-zulip-code).

#### Ubuntu

##### 1. Install Vagrant, Docker, and Git

```
christie@ubuntu-desktop:~
$ sudo apt install vagrant docker.io git
```

##### 2. Add yourself to the `docker` group:

```
christie@ubuntu-desktop:~
$ sudo adduser $USER docker
Adding user `christie' to group `docker' ...
Adding user christie to group docker
Done.
```

You will need to reboot for this change to take effect.  If it worked,
you will see `docker` in your list of groups:

```
christie@ubuntu-desktop:~
$ groups | grep docker
christie adm cdrom sudo dip plugdev lpadmin sambashare docker
```

##### 3. Make sure the Docker daemon is running:

If you had previously installed and removed an older version of
Docker, an [Ubuntu
bug](https://bugs.launchpad.net/ubuntu/+source/docker.io/+bug/1844894)
may prevent Docker from being automatically enabled and started after
installation.  You can check using the following:

```
$ systemctl status docker
● docker.service - Docker Application Container Engine
   Loaded: loaded (/lib/systemd/system/docker.service; enabled; vendor preset: enabled)
   Active: active (running) since Mon 2019-07-15 23:20:46 IST; 18min ago
```

If the service is not running, you'll see `Active: inactive (dead)` on
the second line, and will need to enable and start the Docker service
using the following:

```
sudo systemctl unmask docker
sudo systemctl enable docker
sudo systemctl start docker
```

Now you are ready for [Step 2: Get Zulip code](#step-2-get-zulip-code).

#### Debian

The setup for Debian is very similar to that [for Ubuntu
above](#ubuntu), except that the `docker.io` package is only available
in Debian 10 and later; for Debian 9, see [Docker CE for
Debian](https://docs.docker.com/install/linux/docker-ce/debian/).

#### Windows 10

```eval_rst
.. note::
    We now recommend using `WSL 2 for Windows development <../development/setup-advanced.html#installing-directly-on-windows-10-experimental>`_.
```

1. Install [Git for Windows][git-bash], which installs *Git BASH*.
2. Install [VirtualBox][vbox-dl] (latest).
3. Install [Vagrant][vagrant-dl] (latest).

(Note: While *Git BASH* is recommended, you may also use [Cygwin][cygwin-dl].
If you do, make sure to **install default required packages** along with
**git**, **curl**, **openssh**, and **rsync** binaries.)

Also, you must have hardware virtualization enabled (VT-x or AMD-V) in your
computer's BIOS.

#### Running Git BASH as an administrator

It is important that you **always run Git BASH with administrator
privileges** when working on Zulip code, as not doing so will cause
errors in the development environment (such as symlink creation). You
might wish to configure your Git BASH shortcut to always run with
these privileges enabled (see this [guide][bash-admin-setup] for how
to set this up).

##### Enable native symlinks

The Zulip code includes symbolic links (symlinks). By default, native Windows
symlinks are not enabled in either Git BASH or Cygwin, so you need to do a bit
of configuration. **You must do this before you clone the Zulip code.**

In **Git for BASH**:

Open **Git BASH as an administrator** and run:

```
$ git config --global core.symlinks true
```

Now confirm the setting:

```
$ git config core.symlinks
true
```

If you see `true`, you are ready for [Step 2: Get Zulip
code](#step-2-get-zulip-code).

Otherwise, if the above command prints `false` or nothing at all, then symlinks
have not been enabled.

In **Cygwin**:

Open a Cygwin window **as an administrator** and do this:

```
christie@win10 ~
$ echo 'export "CYGWIN=$CYGWIN winsymlinks:native"' >> ~/.bash_profile
```

Next, close that Cygwin window and open another. If you `echo` $CYGWIN you
should see:

```
christie@win10 ~
$ echo $CYGWIN
winsymlinks:native
```

Now you are ready for [Step 2: Get Zulip code](#step-2-get-zulip-code).

(Note: The **GitHub Desktop client** for Windows has a bug where it
will automatically set `git config core.symlink false` on a repository
if you use it to clone a repository, which will break the Zulip
development environment, because we use symbolic links.  For that
reason, we recommend avoiding using GitHub Desktop client to clone
projects and to instead follow these instructions exactly.)

### Step 2: Get Zulip code

1. In your browser, visit <https://github.com/zulip/zulip>
   and click the `fork` button. You will need to be logged in to GitHub to
   do this.
2. Open Terminal (macOS/Ubuntu) or Git BASH (Windows; must
   **run as an Administrator**).
3. In Terminal/Git BASH,
   [clone your fork of the Zulip repository](../git/cloning.html#step-1b-clone-to-your-machine) and
   [connect the Zulip upstream repository](../git/cloning.html#step-1c-connect-your-fork-to-zulip-upstream):

```
git clone --config pull.rebase git@github.com:YOURUSERNAME/zulip.git
cd zulip
git remote add -f upstream https://github.com/zulip/zulip.git
```

This will create a 'zulip' directory and download the Zulip code into it.

Don't forget to replace YOURUSERNAME with your Git username. You will see
something like:

```
christie@win10 ~
$ git clone --config pull.rebase git@github.com:YOURUSERNAME/zulip.git
Cloning into 'zulip'...
remote: Counting objects: 73571, done.
remote: Compressing objects: 100% (2/2), done.
remote: Total 73571 (delta 1), reused 0 (delta 0), pack-reused 73569
Receiving objects: 100% (73571/73571), 105.30 MiB | 6.46 MiB/s, done.
Resolving deltas: 100% (51448/51448), done.
Checking connectivity... done.
Checking out files: 100% (1912/1912), done.`
```

Now you are ready for [Step 3: Start the development
environment](#step-3-start-the-development-environment).

### Step 3: Start the development environment

Change into the zulip directory and tell vagrant to start the Zulip
development environment with `vagrant up`:

```
# On Windows or macOS:
cd zulip
vagrant plugin install vagrant-vbguest
vagrant up --provider=virtualbox

# On Linux:
cd zulip
vagrant up --provider=docker
```

The first time you run this command it will take some time because vagrant
does the following:

- downloads the base Ubuntu 18.04 virtual machine image (for macOS and Windows)
  or container (for Ubuntu)
- configures this virtual machine/container for use with Zulip,
- creates a shared directory mapping your clone of the Zulip code inside the
  virtual machine/container at `~/zulip`
- runs the `tools/provision` script inside the virtual machine/container, which
  downloads all required dependencies, sets up the python environment for
  the Zulip development server, and initializes a default test
  database.  We call this process "provisioning", and it is documented
  in some detail in our [dependencies documentation](../subsystems/dependencies.md).

You will need an active internet connection during the entire
process. (See [Specifying a proxy](#specifying-a-proxy) if you need a
proxy to access the internet.) `vagrant up` can fail while
provisioning if your Internet connection is unreliable.  To retry, you
can use `vagrant provision` (`vagrant up` will just boot the guest
without provisioning after the first time).  Other common issues are
documented in the
[Troubleshooting and Common Errors](#troubleshooting-and-common-errors)
section.  If that doesn't help, please visit
[#provision help](https://chat.zulip.org/#narrow/stream/21-provision-help)
in the [Zulip development community server](../contributing/chat-zulip-org.md) for
real-time help.

On Windows, you will see the message `The system cannot find the path
specified.` several times.  This is normal and is not a problem.

Once `vagrant up` has completed, connect to the development
environment with `vagrant ssh`:

```
christie@win10 ~/zulip
$ vagrant ssh
```

You should see output that starts like this:

```
Welcome to Ubuntu 18.04.2 LTS (GNU/Linux 4.15.0-54-generic x86_64)
```

Congrats, you're now inside the Zulip development environment!

You can confirm this by looking at the command prompt, which starts
with `(zulip-py3-venv)vagrant@`.  If it just starts with `vagrant@`, your
provisioning failed and you should look at the
[troubleshooting section](#troubleshooting-and-common-errors).

Next, start the Zulip server:

```
(zulip-py3-venv) vagrant@ubuntu-bionic:/srv/zulip
$ ./tools/run-dev.py
```

You will see several lines of output starting with something like:

```
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

```
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

```
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
browser.  More details on how this works are available below.

Zulip's whitespace rules are all enforced by linters, so be sure to
run `tools/lint` often to make sure you're following our coding style
(or use `tools/setup-git-repo` to run it on just the changed files
automatically whenever you commit).

#### Understanding run-dev.py debugging output

It's good to have the terminal running `run-dev.py` up as you work since error
messages including tracebacks along with every backend request will be printed
there.

See [Logging](../subsystems/logging.md) for further details on the run-dev.py console
output.

#### Committing and pushing changes with Git

When you're ready to commit or push changes via Git, you will do this by
running Git commands in Terminal (macOS/Ubuntu) or Git BASH (Windows) in the
directory where you cloned Zulip on your main machine.

If you're new to working with Git/GitHub, check out our [Git & GitHub
Guide][rtd-git-guide].

#### Maintaining the development environment

If after rebasing onto a new version of the Zulip server, you receive
new errors while starting the Zulip server or running tests, this is
probably not because Zulip's master branch is broken.  Instead, this
is likely because we've recently merged changes to the development
environment provisioning process that you need to apply to your
development environment.  To update your environment, you'll need to
re-provision your vagrant machine using `vagrant provision` (this just
runs `tools/provision` from your Zulip checkout inside the Vagrant
guest); this should complete in about a minute.

After provisioning, you'll want to
[(re)start the Zulip development server](#step-3-start-the-development-environment).

If you run into any trouble, [#provision
help](https://chat.zulip.org/#narrow/stream/21-provision-help) in the
[Zulip development community
server](../contributing/chat-zulip-org.md) is a great place to ask for
help.

#### Rebuilding the development environment

If you ever want to recreate your development environment again from
scratch (e.g. to test a change you've made to the provisioning
process, or because you think something is broken), you can do so
using `vagrant destroy` and then `vagrant up`.  This will usually be
much faster than the original `vagrant up` since the base image is
already cached on your machine (it takes about 5 minutes to run with a
fast Internet connection).

Any additional programs (e.g. Zsh, emacs, etc.) or configuration that
you may have installed in the development environment will be lost
when you recreate it.  To address this, you can create a script called
`tools/custom_provision` in your Zulip Git checkout; and place any
extra setup commands there.  Vagrant will run `tools/custom_provision`
every time you run `vagrant provision` (or create a Vagrant guest via
`vagrant up`).

#### Shutting down the development environment for use later

To shut down but preserve the development environment so you can use
it again later use `vagrant halt` or `vagrant suspend`.

You can do this from the same Terminal/Git BASH window that is running
run-dev.py by pressing ^C to halt the server and then typing `exit`. Or you
can halt vagrant from another Terminal/Git BASH window.

From the window where run-dev.py is running:

```
2016-05-04 18:33:13,330 INFO     127.0.0.1       GET     200  92ms /register/ (unauth@zulip via ?)
^C
KeyboardInterrupt
(zulip-py3-venv) vagrant@ubuntu-bionic:/srv/zulip$ exit
logout
Connection to 127.0.0.1 closed.
christie@win10 ~/zulip
```
Now you can suspend the development environment:

```
christie@win10 ~/zulip
$ vagrant suspend
==> default: Saving VM state and suspending execution...
```

If `vagrant suspend` doesn't work, try `vagrant halt`:

```
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

```
christie@win10 ~/zulip
$ vagrant up
$ vagrant ssh

(zulip-py3-venv) vagrant@ubuntu-bionic:/srv/zulip
$ ./tools/run-dev.py
```

### Next steps

Next, read the following to learn more about developing for Zulip:

* [Git & GitHub Guide][rtd-git-guide]
* [Using the development environment][rtd-using-dev-env]
* [Testing][rtd-testing] (and [Configuring CI][ci] to
run the full test suite against any branches you push to your fork,
which can help you optimize your development workflow).

### Troubleshooting and common errors

Below you'll find a list of common errors and their solutions.  Most
issues are resolved by just provisioning again (by running
`./tools/provision` (from `/srv/zulip`) inside the Vagrant guest or
equivalently `vagrant provision` from outside).

If these solutions aren't working for you or you encounter an issue not
documented below, there are a few ways to get further help:

* Ask in [#provision help](https://chat.zulip.org/#narrow/stream/21-provision-help)
  in the [Zulip development community server](../contributing/chat-zulip-org.md).
* [File an issue](https://github.com/zulip/zulip/issues).

When reporting your issue, please include the following information:

* host operating system
* installation method (Vagrant or direct)
* whether or not you are using a proxy
* a copy of Zulip's `vagrant` provisioning logs, available in
  `/var/log/provision.log` on your virtual machine.  If you choose to
  post just the error output, please include the **beginning of the
  error output**, not just the last few lines.

The output of `tools/diagnose` run inside the Vagrant guest is also
usually helpful.

#### Vagrant guest doesn't show (zulip-py3-venv) at start of prompt

This is caused by provisioning failing to complete successfully.  You
can see the errors in `var/log/provision.log`; it should end with
something like this:

```
ESC[94mZulip development environment setup succeeded!ESC[0m
```

The `ESC` stuff are the terminal color codes that make it show as a nice
blue in the terminal, which unfortunately looks ugly in the logs.

If you encounter an incomplete `/var/log/provision.log file`, you need to
update your environment. Re-provision your vagrant machine; if the problem
persists, please come chat with us (see instructions above) for help.

After you provision successfully, you'll need to exit your `vagrant ssh`
shell and run `vagrant ssh` again to get the virtualenv setup properly.

#### Vagrant was unable to mount VirtualBox shared folders

For the following error:
```
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

```
vagrant halt
vagrant up
```

to reboot the guest.  After this, you can do `vagrant provision` and
`vagrant ssh`.

#### ssl read error

If you receive the following error while running `vagrant up`:

```
SSL read: error:00000000:lib(0):func(0):reason(0), errno 104
```

It means that either your network connection is unstable and/or very
slow. To resolve it, run `vagrant up` until it works (possibly on a
better network connection).

#### Unmet dependencies error

When running `vagrant up` or `provision`, if you see the following error:

```
==> default: E:unmet dependencies. Try 'apt-get -f install' with no packages (or specify a solution).
```

It means that your local apt repository has been corrupted, which can
usually be resolved by executing the command:

```
apt-get -f install
```

#### ssh connection closed by remote host

On running `vagrant ssh`, if you see the following error:

```
ssh_exchange_identification: Connection closed by remote host
```

It usually means the Vagrant guest is not running, which is usually
solved by rebooting the Vagrant guest via `vagrant halt; vagrant up`.  See
[Vagrant was unable to communicate with the guest machine](#vagrant-was-unable-to-communicate-with-the-guest-machine)
for more details.

#### os.symlink error

If you receive the following error while running `vagrant up`:

```
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
create symbolic links on Windows.  Additionally [UAC][windows-uac], a
Windows feature intended to limit the impact of malware, can prevent
even administrator accounts from creating symlinks.  [Turning off
UAC][disable-uac] will allow you to create symlinks. You can also try
some of the solutions mentioned
[here](https://superuser.com/questions/124679/how-do-i-create-a-link-in-windows-7-home-premium-as-a-regular-user).

[windows-uac]: https://docs.microsoft.com/en-us/windows/security/identity-protection/user-account-control/how-user-account-control-works
[disable-uac]: https://stackoverflow.com/questions/15320550/why-is-secreatesymboliclinkprivilege-ignored-on-windows-8

If you ran Git BASH as administrator but you already had VirtualBox
running, you might still get this error because VirtualBox is not
running as administrator.  In that case: close the Zulip VM with
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

```
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

```
vboxmanage setextradata YOURVMNAME VBoxInternal2/SharedFoldersEnableSymlinksCreate/srv_zulip 1
```

The virtual machine needs to be shut down when you run this command.

#### Hyper-V error messages

If you get an error message on Windows about lack of Windows Home
support for Hyper-V when running `vagrant up`, the problem is that
Windows is incorrectly attempting to use Hyper-V rather than
Virtualbox as the virtualization provider.  You can fix this by
explicitly passing the virtualbox provider to `vagrant up`:

```
christie@win10 ~/zulip
$ vagrant up --provide=virtualbox
```

#### Connection timeout on `vagrant up`

If you see the following error after running `vagrant up`:

```
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

For further information about troubleshooting vagrant timeout errors [see
this post](https://stackoverflow.com/questions/22575261/vagrant-stuck-connection-timeout-retrying#22575302).

#### Vagrant was unable to communicate with the guest machine

If you see the following error when you run `vagrant up`:

```
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
Virtualbox or Vagrant.  If you see this error, you usually can fix it
by rebooting the guest via `vagrant halt; vagrant up`.

#### Vagrant up fails with subprocess.CalledProcessError

The `vagrant up` command basically does the following:

* Downloads an Ubuntu image and starts it using a Vagrant provider.
* Uses `vagrant ssh` to connect to that Ubuntu guest, and then runs
  `tools/provision`, which has a lot of subcommands that are
  executed via Python's `subprocess` module.  These errors mean that
  one of those subcommands failed.

To debug such errors, you can log in to the Vagrant guest machine by
running `vagrant ssh`, which should present you with a standard shell
prompt.  You can debug interactively by using e.g. `cd zulip &&
./tools/provision`, and then running the individual subcommands
that failed.  Once you've resolved the problem, you can rerun
`tools/provision` to proceed; the provisioning system is designed
to recover well from failures.

The Zulip provisioning system is generally highly reliable; the most common
cause of issues here is a poor network connection (or one where you need a
proxy to access the Internet and haven't [configured the development
environment to use it](#specifying-a-proxy).

Once you've provisioned successfully, you'll get output like this:
```
Zulip development environment setup succeeded!
(zulip-py3-venv) vagrant@vagrant-base-trusty-amd64:~/zulip$
```

If the `(zulip-py3-venv)` part is missing, this is because your
installation failed the first time before the Zulip virtualenv was
created.  You can fix this by just closing the shell and running
`vagrant ssh` again, or using `source /srv/zulip-py3-venv/bin/activate`.

Finally, if you encounter any issues that weren't caused by your
Internet connection, please report them!  We try hard to keep Zulip
development environment provisioning free of bugs.

##### `pip install` fails during `vagrant up` on Ubuntu

Likely causes are:

1. Networking issues
2. Insufficient RAM. Check whether you've allotted at least two
gigabytes of RAM, which is the minimum Zulip
[requires](../development/setup-vagrant.html#requirements). If
not, go to your VM settings and increase the RAM, then restart
the VM.

##### yarn install warnings

```
$ yarn install
yarn install v0.24.5
[1/4] Resolving packages...
[2/4] Fetching packages...
warning fsevents@1.1.1: The platform "linux" is incompatible with this module.
info "fsevents@1.1.1" is an optional dependency and failed compatibility check. Excluding it from installation.
[3/4] Linking dependencies...
[4/4] Building fresh packages...
Done in 23.50s.
```

These are warnings produced by spammy third party JavaScript packages.
It is okay to proceed and start the Zulip server.

#### VBoxManage errors related to VT-x or WHvSetupPartition

```
There was an error while executing `VBoxManage`, a CLI used by Vagrant
for controlling VirtualBox. The command and stderr is shown below.

Command: ["startvm", "8924a681-b4e4-4b7a-96f2-4cb11619f123", "--type", "headless"]

Stderr: VBoxManage.exe: error: (VERR_NEM_MISSING_KERNEL_API).
VBoxManage.exe: error: VT-x is not available (VERR_VMX_NO_VMX)
VBoxManage.exe: error: Details: code E_FAIL (0x80004005), component ConsoleWrap, interface IConsole
```

or

```
Stderr: VBoxManage.exe: error: Call to WHvSetupPartition failed: ERROR_SUCCESS (Last=0xc000000d/87) (VERR_NEM_VM_CREATE_FAILED)
VBoxManage.exe: error: Details: code E_FAIL (0x80004005), component ConsoleWrap, interface IConsole
```

First, ensure that hardware virtualization support (VT-x or AMD-V) is
enabled in your BIOS.

If the error persists, you may have run into an incompatibility
between VirtualBox and Hyper-V on Windows.  To disable Hyper-V, open
command prompt as administrator, run `bcdedit /set
hypervisorlaunchtype off`, and reboot.  If you need to enable it
later, run `bcdedit /deletevalue hypervisorlaunchtype`, and reboot.

#### OSError: [Errno 26] Text file busy

```
default: Traceback (most recent call last):
…
default:   File "/srv/zulip-py3-venv/lib/python3.6/shutil.py", line 426, in _rmtree_safe_fd
default:     os.rmdir(name, dir_fd=topfd)
default: OSError: [Errno 26] Text file busy: 'baremetrics'
```

This error is caused by a
[bug](https://www.virtualbox.org/ticket/19004) in recent versions of
the VirtualBox Guest Additions for Linux on Windows hosts.  It has not
been fixed upstream as of this writing, but you may be able to work
around it by downgrading VirtualBox Guest Additions to 6.0.4.  To do
this, create a `~/.zulip-vagrant-config` file and add this line:

```
VBOXADD_VERSION 6.0.4
```

Then run these commands (yes, reload is needed twice):

```
vagrant plugin install vagrant-vbguest
vagrant reload
vagrant reload --provision
```

### Specifying an Ubuntu mirror

Bringing up a development environment for the first time involves
downloading many packages from the Ubuntu archive.  The Ubuntu cloud
images use the global mirror `http://archive.ubuntu.com/ubuntu/` by
default, but you may find that you can speed up the download by using
a local mirror closer to your location.  To do this, create
`~/.zulip-vagrant-config` and add a line like this, replacing the URL
as appropriate:

```
UBUNTU_MIRROR http://us.archive.ubuntu.com/ubuntu/
```

### Specifying a proxy

If you need to use a proxy server to access the Internet, you will
need to specify the proxy settings before running `Vagrant up`.
First, install the Vagrant plugin `vagrant-proxyconf`:

```
vagrant plugin install vagrant-proxyconf
```

Then create `~/.zulip-vagrant-config` and add the following lines to
it (with the appropriate values in it for your proxy):

```
HTTP_PROXY http://proxy_host:port
HTTPS_PROXY http://proxy_host:port
NO_PROXY localhost,127.0.0.1,.example.com,.zulipdev.com
```

For proxies that require authentication, the config will be a bit more
complex, e.g.:

```
HTTP_PROXY http://userName:userPassword@192.168.1.1:8080
HTTPS_PROXY http://userName:userPassword@192.168.1.1:8080
NO_PROXY localhost,127.0.0.1,.example.com,.zulipdev.com
```

You'll want to **double-check** your work for mistakes (a common one
is using `https://` when your proxy expects `http://`).  Invalid proxy
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
adding to your `~/.zulip-vagrant-config` file.  E.g. if you set:

```
HOST_PORT 9971
```

(and `vagrant reload` to apply the new configuration), then you would visit
http://localhost:9971/ to connect to your development server.

If you'd like to be able to connect to your development environment from other
machines than the VM host, you can manually set the host IP address in the
'~/.zulip-vagrant-config' file as well. For example, if you set:

```
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

Our default Vagrant settings allocate 2 cpus with 2GiB of memory for
the guest, which is sufficient to run everything in the development
environment.  If your host system has more CPUs, or you have enough
RAM that you'd like to allocate more than 2GiB to the guest, you can
improve performance of the Zulip development environment by allocating
more resources.

To do so, create a `~/.zulip-vagrant-config` file containing the
following lines:

```
GUEST_CPUS <number of cpus>
GUEST_MEMORY_MB <system memory (in MB)>
```

For example:

```
GUEST_CPUS 4
GUEST_MEMORY_MB 8192
```

would result in an allocation of 4 cpus and 8 GiB of memory to the
guest VM.

After changing the configuration, run `vagrant reload` to reboot the
guest VM with your new configuration.

If at any time you wish to revert back to the default settings, simply
remove the `GUEST_CPUS` and `GUEST_MEMORY_MB` lines from
`~/.zulip-vagrant-config`.

[cygwin-dl]: https://cygwin.com/
[vagrant-dl]: https://www.vagrantup.com/downloads.html
[vbox-dl]: https://www.virtualbox.org/wiki/Downloads
[vmware-fusion-dl]: https://www.vmware.com/products/fusion.html
[vagrant-vmware-fusion-dl]: https://www.vagrantup.com/vmware/
[parallels-desktop-dl]: https://www.parallels.com/products/desktop/
[install-advanced]: ../development/setup-advanced.md
[rtd-git-guide]: ../git/index.md
[rtd-testing]: ../testing/testing.md
[rtd-using-dev-env]: using.md
[rtd-dev-remote]: remote.md
[git-bash]: https://git-for-windows.github.io/
[bash-admin-setup]: https://superuser.com/questions/1002262/run-applications-as-administrator-by-default-in-windows-10
[set-up-git]: ../git/setup.md
[ci]: ../git/cloning.html#step-3-configure-continuous-integration-for-your-fork
