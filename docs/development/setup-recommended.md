## Recommended environment setup tutorial

This section guides first-time contributors through installing the
Zulip development environment on Windows, macOS, and Linux.

The recommended method for installing the Zulip development environment is
to use WSL 2 on Windows, and Vagrant with Docker on macOS and Linux.

All of these recommended methods work by creating a container or VM
for the Zulip server and related services, with the Git repository
containing your source code mounted inside it. This strategy allows
the environment to be as reliable and portable as possible. The
specific technologies (Vagrant/Docker and WSL 2) were chosen based on
what technologies have been most reliable through our experience
supporting the thousands of people who've set up the Zulip development
environment.

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

### Requirements

Installing the Zulip development environment requires downloading several
hundred megabytes of dependencies. You will need an active internet
connection throughout the entire installation processes. (See
[Specifying a proxy](#specifying-a-proxy) if you need a proxy to access
the internet.)

- 2GB available RAM
- active broadband internet connection
- [GitHub account](#step-0-set-up-git--github)

::::{tab-set}

:::{tab-item} Windows
:sync: os-windows
:name: windows-10-or-11

- Windows 64-bit (Windows 10 recommended)
- hardware virtualization enabled (VT-x or AMD-V)
- administrator access
  :::

:::{tab-item} macOS
:sync: os-mac

- macOS (10.11 El Capitan or newer recommended)
  :::

:::{tab-item} Ubuntu/Debian
:sync: os-ubuntu

- Ubuntu 22.04, or 24.04
- Debian 12
  :::

:::{tab-item} Fedora
:sync: os-fedora

- tested for Fedora 36
  :::

:::{tab-item} Other Linux
:sync: os-other-linux

- Any Linux distribution should work, if it supports Git, Vagrant and
  Docker. We don't maintain documentation for installing Vagrant,
  Docker, and other dependencies on those systems, so you'll want to
  roughly follow the Ubuntu/Debian instructions, using upstream
  documentation for installing dependencies.
  :::

::::

### Step 0: Set up Git & GitHub

You can skip this step if you already have Git, GitHub, and SSH access
to GitHub working on your machine.

Follow our [Git guide][set-up-git] in order to install Git, set up a
GitHub account, create an SSH key to access code on GitHub
efficiently, etc. Be sure to create an SSH key and add it to your
GitHub account using
[these instructions](https://docs.github.com/en/authentication/connecting-to-github-with-ssh).

### Step 1: Install prerequisites

::::{tab-set}

:::{tab-item} Windows
:sync: os-windows

Zulip's development environment is most easily set up on Windows using
the Windows Subsystem for Linux ([WSL
2](https://learn.microsoft.com/en-us/windows/wsl/compare-versions))
installation method described here. We require version 0.67.6+ of WSL 2.

1. Enable virtualization through your BIOS settings. This sequence
   depends on your specific hardware and brand, but here are [some
   basic instructions.][windows-bios-virtualization]

1. [Install WSL
   2](https://docs.microsoft.com/en-us/windows/wsl/setup/environment),
   which includes installing an Ubuntu WSL distribution. Using an
   existing distribution will probably work, but [a fresh
   distribution](#rebuilding-the-development-environment) is
   recommended if you previously installed other software in your WSL
   environment that might conflict with the Zulip environment.

1. It is required to enable `systemd` for WSL 2 to manage the database, cache and other services.
   To configure it, please follow [these instructions](https://learn.microsoft.com/en-us/windows/wsl/wsl-config#systemd-support).
   Then, you will need to restart WSL 2 before continuing.

1. Launch the Ubuntu shell as an administrator and run the following command:

   ```console
   $ sudo apt update && sudo apt upgrade
   ```

1. Install dependencies with the following command:

   ```console
   $ sudo apt install rabbitmq-server memcached redis-server postgresql
   ```

1. Open `/etc/rabbitmq/rabbitmq-env.conf` using, for example:

   ```console
   $ sudo nano /etc/rabbitmq/rabbitmq-env.conf
   ```

   Confirm the following lines are at the end of your file, and add
   them if not present:

   ```ini
   NODE_IP_ADDRESS=127.0.0.1
   NODE_PORT=5672
   ```

   Then save your changes (`Ctrl+O`, then `Enter` to confirm the path),
   and exit `nano` (`Ctrl+X`).

1. Run the command below to make sure you are inside the WSL disk and not
   in a Windows mounted disk. You will run into permission issues if you
   run `./tools/provision` from `zulip` in a Windows mounted disk.

   ```console
   $ cd ~  # or cd /home/USERNAME
   ```

1. [Create a new SSH key][create-ssh-key] for the WSL 2 virtual
   machine and add it to your GitHub account. Note that SSH keys
   linked to your Windows computer will not work within the virtual
   machine.

WSL 2 can be uninstalled by following [Microsoft's documentation][uninstall-wsl]

[create-ssh-key]: https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account
[uninstall-wsl]: https://learn.microsoft.com/en-us/windows/wsl/faq#how-do-i-uninstall-a-wsl-distribution-
[windows-bios-virtualization]: https://www.thewindowsclub.com/disable-hardware-virtualization-in-windows-10

:::

:::{tab-item} macOS
:sync: os-mac

1. Install [Vagrant][vagrant-dl] (latest).
2. Install [Docker Desktop](https://docs.docker.com/desktop/mac/install/) (latest).
3. Open the Docker desktop app's settings panel, and choose `osxfs (legacy)` under "Choose file sharing implementation for your containers."
   :::

:::{tab-item} Ubuntu/Debian
:sync: os-ubuntu

##### 1. Install Vagrant, Docker, and Git

Install vagrant:

```console
$ wget -O - https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
$ echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
$ sudo apt update && sudo apt install vagrant
```

Install Docker and Git:

```console
$ sudo apt install docker.io git
```

```{include} setup/install-docker.md

```

:::

:::{tab-item} Fedora
:sync: os-fedora

##### 1. Install Vagrant, Docker, and Git

```console
$ sudo yum install vagrant git moby-engine
```

Fedora does not include the
official `docker-ce` package in their repositories. They provide the package
`moby-engine` which you can choose instead. In case you prefer the official
docker distribution, you can follow
[their documentation to install Docker on Fedora](https://docs.docker.com/engine/install/fedora/).

```{include} setup/install-docker.md

```

:::

::::

### Step 2: Get Zulip code

1. In your browser, visit <https://github.com/zulip/zulip>
   and click the **Fork** button. You will need to be logged in to GitHub to
   do this.
2. Open Terminal (macOS/Linux) or Git BASH (Windows; must
   **run as an Administrator**).
3. In Terminal/Git BASH,
   [clone your fork of the Zulip repository](../git/cloning.md#step-1b-clone-to-your-machine) and
   [connect the Zulip upstream repository](../git/cloning.md#step-1c-connect-your-fork-to-zulip-upstream):

```console
$ git clone --config pull.rebase git@github.com:YOURUSERNAME/zulip.git
$ cd zulip
$ git remote add -f upstream https://github.com/zulip/zulip.git
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

### Step 3: Start the development environment

::::{tab-set}

:::{tab-item} Windows (WSL)
:sync: os-windows

Run the following to install the Zulip development environment and
start it. (If Windows Firewall creates popups to block services,
simply click **Allow access**.)

```console
$ # Install/update the Zulip development environment
$ ./tools/provision
$ # Enter the Zulip Python environment
$ source .venv/bin/activate
$ # Start the development server
$ ./tools/run-dev
```

If you are facing problems or you see error messages after running `./tools/run-dev`,
you can try running `./tools/provision` again.
:::

:::{tab-item} Windows (VM)
:sync: os-windows-vm

Change into the zulip directory and tell Vagrant to start the Zulip
development environment with `vagrant up`:

```console
$ cd zulip
$ vagrant plugin install vagrant-vbguest
$ vagrant up --provider=virtualbox
```

```{include} setup/vagrant-up.md

```

On Windows, you will see the message
`The system cannot find the path specified.` several times. This is
normal and is not a problem.

```{include} setup/vagrant-ssh.md

```

:::

:::{tab-item} macOS
:sync: os-mac

Change into the zulip directory and tell Vagrant to start the Zulip
development environment with `vagrant up`:

```console
$ cd zulip
$ vagrant up --provider=docker
```

**Important note**: There is a [known upstream issue on
macOS](https://chat.zulip.org/#narrow/channel/21-provision-help/topic/provision.20error.20ERR_PNPM_LINKING_FAILED/near/1649241)
that can cause provisioning to fail with `ERR_PNPM_LINKING_FAILED` or
other errors. The temporary fix is to open the Docker desktop app's
settings panel, and choose `osxfs (legacy)` under "Choose file sharing
implementation for your containers." Once Docker restarts, you should
be able to successfully run `vagrant up --provider=docker`. Back in
Docker, you can return to using VirtioFS for better system performance
while developing, but you may need to revert to `osxfs (legacy)`
whenever you need to re-provision.

```{include} setup/vagrant-up.md

```

```{include} setup/vagrant-ssh.md

```

:::

:::{tab-item} Ubuntu/Debian
:sync: os-ubuntu

Change into the zulip directory and tell Vagrant to start the Zulip
development environment with `vagrant up`:

```console
$ cd zulip
$ vagrant up --provider=docker
```

```{include} setup/vagrant-up.md

```

```{include} setup/vagrant-ssh.md

```

:::

:::{tab-item} Fedora
:sync: os-fedora

Change into the zulip directory and tell Vagrant to start the Zulip
development environment with `vagrant up`:

```console
$ cd zulip
$ vagrant up --provider=docker
```

```{include} setup/vagrant-up.md

```

```{include} setup/vagrant-ssh.md

```

:::

::::

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

#### VSCode setup (optional)

::::{tab-set}

:::{tab-item} Windows (WSL)
:sync: os-windows

The [Visual Studio Code Remote -
WSL](https://code.visualstudio.com/docs/remote/wsl) extension is
recommended for editing files when developing with WSL. When you
have it installed, you can run:

```console
$ code .
```

to open VS Code connected to your WSL environment. See the [Remote development in WSL][remote-wsl] tutorial for more information.
:::

:::{tab-item} Windows (VM)
:sync: os-windows-vm

```{include} setup/vscode-vagrant.md

```

:::

:::{tab-item} macOS
:sync: os-mac

```{include} setup/vscode-vagrant.md

```

:::

:::{tab-item} Ubuntu/Debian
:sync: os-ubuntu

```{include} setup/vscode-vagrant.md

```

:::

:::{tab-item} Fedora
:sync: os-fedora

```{include} setup/vscode-vagrant.md

```

:::

::::

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

::::{tab-set}

:::{tab-item} Windows (WSL)
:sync: os-windows

If after rebasing onto a new version of the Zulip server, you receive
new errors while starting the Zulip server or running tests, this is
probably not because Zulip's `main` branch is broken. Instead, this
is likely because we've recently merged changes to the development
environment provisioning process that you need to apply to your
development environment. To update your environment, you'll need to
re-provision using `tools/provision` from your Zulip checkout; this
should complete in about a minute.

After provisioning, you'll want to
[(re)start the Zulip development server](/development/setup-recommended.md#step-3-start-the-development-environment).

If you run into any trouble, [#provision
help](https://chat.zulip.org/#narrow/channel/21-provision-help) in the
[Zulip development community
server](https://zulip.com/development-community/) is a great place to ask for
help.

:::

:::{tab-item} Windows (VM)
:sync: os-windows-vm

```{include} setup/vagrant-update.md

```

:::

:::{tab-item} macOS
:sync: os-mac

```{include} setup/vagrant-update.md

```

:::

:::{tab-item} Ubuntu/Debian
:sync: os-ubuntu

```{include} setup/vagrant-update.md

```

:::

:::{tab-item} Fedora
:sync: os-fedora

```{include} setup/vagrant-update.md

```

:::

::::

#### Rebuilding the development environment

::::{tab-set}

:::{tab-item} Windows (WSL)
:sync: os-windows

```{include} setup/wsl-rebuild.md

```

:::

:::{tab-item} Windows (VM)
:sync: os-windows-vm

```{include} setup/vagrant-rebuild.md

```

:::

:::{tab-item} macOS
:sync: os-mac

```{include} setup/vagrant-rebuild.md

```

:::

:::{tab-item} Ubuntu/Debian
:sync: os-ubuntu

```{include} setup/vagrant-rebuild.md

```

:::

:::{tab-item} Fedora
:sync: os-fedora

```{include} setup/vagrant-rebuild.md

```

:::

::::

#### Shutting down the development environment for use later

::::{tab-set}

:::{tab-item} Windows (WSL)
:sync: os-windows

On Windows with WSL 2, you do not need to shut down the environment. Simply
close your terminal window(s).

Alternatively, you can use a command to terminate/shutdown your WSL2 environment with PowerShell using:

```console
> wsl --terminate <environment_name>
```

:::

:::{tab-item} Windows (VM)
:sync: os-windows-vm

```{include} setup/vagrant-halt.md

```

:::

:::{tab-item} macOS
:sync: os-mac

```{include} setup/vagrant-halt.md

```

:::

:::{tab-item} Ubuntu/Debian
:sync: os-ubuntu

```{include} setup/vagrant-halt.md

```

:::

:::{tab-item} Fedora
:sync: os-fedora

```{include} setup/vagrant-halt.md

```

:::

::::

#### Resuming the development environment

::::{tab-set}

:::{tab-item} Windows (WSL)
:sync: os-windows

On Windows with WSL 2, to resume developing you just need to open a new Git
BASH window. Then change into your `zulip` folder and verify the Python
environment was properly activated (you should see `(zulip-server)`). If the
`(zulip-server)` part is missing, run:

```console
$ source .venv/bin/activate
```

:::

:::{tab-item} Windows (VM)
:sync: os-windows-vm

```{include} setup/vagrant-resume.md

```

:::

:::{tab-item} macOS
:sync: os-mac

```{include} setup/vagrant-resume.md

```

:::

:::{tab-item} Ubuntu/Debian
:sync: os-ubuntu

```{include} setup/vagrant-resume.md

```

:::

:::{tab-item} Fedora
:sync: os-fedora

```{include} setup/vagrant-resume.md

```

:::

::::

### Next steps

Next, read the following to learn more about developing for Zulip:

- [Git & GitHub guide][rtd-git-guide]
- [Using the development environment][rtd-using-dev-env]
- [Testing][rtd-testing] (and [Configuring CI][ci] to
  run the full test suite against any branches you push to your fork,
  which can help you optimize your development workflow).

### Troubleshooting and common errors

Below you'll find a list of common errors and their solutions. Most
issues are resolved by just provisioning again by running
`./tools/provision` (from `/srv/zulip`) inside the Vagrant guest (or
equivalently `vagrant provision` from outside) or by running
`./tools/provision` in `~/zulip` inside the WSL instance.

If these solutions aren't working for you or you encounter an issue not
documented below, there are a few ways to get further help:

- Ask in [#provision help](https://chat.zulip.org/#narrow/channel/21-provision-help)
  in the [Zulip development community server](https://zulip.com/development-community/).
- [File an issue](https://github.com/zulip/zulip/issues).

When reporting your issue, please include the following information:

- The host operating system
- The installation method (e.g., Vagrant or WSL)
- Whether or not you are using a proxy
- A copy of Zulip's `vagrant` provisioning logs, available in
  `/var/log/provision.log` on your virtual machine or
  `~/zulip/var/log/provision.log` on your WSL instance. If you
  choose to post just the error output, please include the
  **beginning of the error output**, not just the last few lines.

The output of `tools/diagnose` (run inside the Vagrant guest or
WSL instance) is also usually helpful.

::::{tab-set}

:::{tab-item} Windows (WSL)
:sync: os-windows

```{include} setup/wsl-troubleshoot.md

```

:::

:::{tab-item} Windows (VM)
:sync: os-windows-vm

```{include} setup/shared-vagrant-errors.md

```

```{include} setup/winvm-troubleshoot.md

```

:::

:::{tab-item} macOS
:sync: os-mac

```{include} setup/shared-vagrant-errors.md

```

```{include} setup/unix-troubleshoot.md

```

:::

:::{tab-item} Ubuntu/Debian
:sync: os-ubuntu

```{include} setup/shared-vagrant-errors.md

```

```{include} setup/unix-troubleshoot.md

```

:::

:::{tab-item} Fedora
:sync: os-fedora

```{include} setup/shared-vagrant-errors.md

```

```{include} setup/unix-troubleshoot.md

```

:::
::::

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

```console
$ vagrant plugin install vagrant-proxyconf
```

Then create `~/.zulip-vagrant-config` and add the following lines to
it (with the appropriate values in it for your proxy):

```text
HTTP_PROXY http://proxy_host:port
HTTPS_PROXY http://proxy_host:port
NO_PROXY localhost,127.0.0.1,.example.com,.zulipdev.com
```

For proxies that require authentication, the config will be a bit more
complex, for example:

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
adding to your `~/.zulip-vagrant-config` file. E.g., if you set:

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
[remote-wsl]: https://code.visualstudio.com/docs/remote/wsl-tutorial
[rtd-git-guide]: ../git/index.md
[rtd-testing]: ../testing/testing.md
[rtd-using-dev-env]: using.md
[rtd-dev-remote]: remote.md
[set-up-git]: ../git/setup.md
[ci]: ../git/cloning.md#step-3-configure-continuous-integration-for-your-fork
