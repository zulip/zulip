# Advanced setup

Contents:

- [Installing directly on Ubuntu, Debian, CentOS, or Fedora](#installing-directly-on-ubuntu-debian-centos-or-fedora)
- [Installing using Vagrant with VirtualBox on Windows 10](#installing-using-vagrant-with-virtualbox-on-windows-10)
- [Using the Vagrant Hyper-V provider on Windows](#using-the-vagrant-hyper-v-provider-on-windows-beta)
- [Newer versions of supported platforms](#newer-versions-of-supported-platforms)

## Installing directly on Ubuntu, Debian, CentOS, or Fedora

:::{warning}
There is no supported uninstallation process with the direct-install
method. If you want that, use [the Vagrant environment](setup-recommended.md),
where you can just do `vagrant destroy` to clean up the development environment.
:::

One can install the Zulip development environment directly on a Linux
host by following these instructions. Currently supported platforms
are:

- Ubuntu 20.04, 22.04
- Debian 11, 12
- CentOS 7 (beta)
- Fedora 38 (beta)
- RHEL 7 (beta)

**Note**: You should not use the `root` user to run the installation.
If you are using a [remote server](remote.md), see
the
[section on creating appropriate user accounts](remote.md#setting-up-user-accounts).

Start by [cloning your fork of the Zulip repository][zulip-rtd-git-cloning]
and [connecting the Zulip upstream repository][zulip-rtd-git-connect]:

```bash
git clone --config pull.rebase git@github.com:YOURUSERNAME/zulip.git
cd zulip
git remote add -f upstream https://github.com/zulip/zulip.git
```

CentOS, Fedora, and RHEL users should ensure that python3 is installed on their
systems (Debian and Ubuntu distributions already include it):

```bash
# On CentOS/Fedora/RHEL, you must first install python3.
# For example, this command installs python3 with yum:
yum install python
```

With python3 installed, change into the directory where you have cloned
Zulip and run the following commands:

```bash
# From inside a clone of zulip.git:
./tools/provision
source /srv/zulip-py3-venv/bin/activate
./tools/run-dev  # starts the development server
```

Once you've done the above setup, you can pick up the [documentation
on using the Zulip development
environment](setup-recommended.md#step-4-developing),
ignoring the parts about `vagrant` (since you're not using it).

## Installing using Vagrant with VirtualBox on Windows 10

:::{note}
We recommend using [WSL 2 for Windows development](setup-recommended.md#windows-10-or-11)
because it is easier to set up and provides a substantially better experience.
:::

1. Install [Git for Windows][git-bash], which installs _Git BASH_.
2. Install [VirtualBox][vbox-dl] (latest).
3. Install [Vagrant][vagrant-dl] (latest).

(Note: While _Git BASH_ is recommended, you may also use [Cygwin][cygwin-dl].
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

```console
$ git config --global core.symlinks true
```

Now confirm the setting:

```console
$ git config core.symlinks
true
```

If you see `true`, you are ready for [Step 2: Get Zulip code](setup-recommended.md#step-2-get-zulip-code).

Otherwise, if the above command prints `false` or nothing at all, then symlinks
have not been enabled.

In **Cygwin**:

Open a Cygwin window **as an administrator** and do this:

```console
christie@win10 ~
$ echo 'export "CYGWIN=$CYGWIN winsymlinks:native"' >> ~/.bash_profile
```

Next, close that Cygwin window and open another. If you `echo` $CYGWIN you
should see:

```console
christie@win10 ~
$ echo $CYGWIN
winsymlinks:native
```

Now you are ready for [Step 2: Get Zulip code](setup-recommended.md#step-2-get-zulip-code).

(Note: The **GitHub Desktop client** for Windows has a bug where it
will automatically set `git config core.symlink false` on a repository
if you use it to clone a repository, which will break the Zulip
development environment, because we use symbolic links. For that
reason, we recommend avoiding using GitHub Desktop client to clone
projects and to instead follow these instructions exactly.)

[cygwin-dl]: https://cygwin.com
[git-bash]: https://git-for-windows.github.io
[vbox-dl]: https://www.virtualbox.org/wiki/Downloads
[vagrant-dl]: https://www.vagrantup.com/downloads.html
[bash-admin-setup]: https://superuser.com/questions/1002262/run-applications-as-administrator-by-default-in-windows-10

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
   (zulip-py3-venv) vagrant@ubuntu-18:/srv/zulip$ ./tools/run-dev
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

2. Be patient the first time you run `./tools/run-dev`.

As with other installation methods, please visit [#provision
help][provision-help] in the [Zulip development community
server](https://zulip.com/development-community/) if you need help.

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
in [the Zulip development community](https://zulip.com/development-community/),
and a core team member can help guide you through adding support for the platform.

[zulip-rtd-git-cloning]: ../git/cloning.md#step-1b-clone-to-your-machine
[zulip-rtd-git-connect]: ../git/cloning.md#step-1c-connect-your-fork-to-zulip-upstream
