Below you'll find a list of common errors and their solutions. Most
issues are resolved by just provisioning again (by running
`./tools/provision` (from `/srv/zulip`) inside the Vagrant guest or
equivalently `vagrant provision` from outside).

If these solutions aren't working for you or you encounter an issue not
documented below, there are a few ways to get further help:

- Ask in [#provision help](https://chat.zulip.org/#narrow/channel/21-provision-help)
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

```console
$ apt-get -f install
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
prompt. You can debug interactively by using, for example,
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
(zulip-py3-venv) vagrant@vagrant:/srv/zulip$
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
   [requires](/development/setup-recommended.md#requirements). If
   not, go to your VM settings and increase the RAM, then restart
   the VM.

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
