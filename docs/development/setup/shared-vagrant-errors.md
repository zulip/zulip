#### Vagrant guest doesn't show (zulip-server) at start of prompt

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

#### ssh connection closed by remote host

On running `vagrant ssh`, if you see the following error:

```console
ssh_exchange_identification: Connection closed by remote host
```

It usually means the Vagrant guest is not running, which is usually
solved by rebooting the Vagrant guest via `vagrant halt; vagrant up`. See
[Vagrant was unable to communicate with the guest machine](/development/setup-recommended.md#vagrant-was-unable-to-communicate-with-the-guest-machine)
for more details.

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
environment to use it](/development/setup-recommended.md#specifying-a-proxy)).

Once you've provisioned successfully, you'll get output like this:

```console
Zulip development environment setup succeeded!
(zulip-server) vagrant@vagrant:/srv/zulip$
```

If the `(zulip-server)` part is missing, this is because your
installation failed the first time before the Zulip virtualenv was
created. You can fix this by just closing the shell and running
`vagrant ssh` again, or using `source .venv/bin/activate`.

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
