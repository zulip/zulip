# Development environment installation

## Requirements

The Zulip development environment can be installed on **macOS,
Windows, and Linux** (Debian or Ubuntu recommended). You'll need at least **2GB
of available RAM**.

Installing the Zulip development environment requires downloading several hundred
megabytes of dependencies, so you will need an **active, reasonably fast,
internet connection throughout the entire installation processes.** You can
[configure a proxy][configure-proxy] if you need one.

## Recommended setup (Vagrant)

**For first-time contributors, we recommend using the
[Vagrant development environment][install-vagrant]**.

This method creates a virtual machine (for Windows and macOS) or a
Linux container (otherwise) inside which the Zulip server and all
related services will run. Vagrant adds a bit of overhead to using the
Zulip development server, but provides an isolated environment that is
easy to install, update, and uninstall. It has been well-tested and
performs well.

## Advanced setup (non-Vagrant)

Zulip also supports a wide range of ways to install the Zulip
development environment:

* On **Ubuntu** 18.04 Bionic, 16.04 Xenial and 14.04 Trusty and **Debian** 9
  Stretch, you can easily
  **[install without using Vagrant][install-direct]**.
* On **other Linux** distributions, you'll need to follow slightly different
  instructions to **[install manually][install-generic]**.
* On **macOS and Linux** (Ubuntu recommended), you can install **[using
  Docker][install-docker]**, though support for this remains experimental.

Unfortunately, the only supported method to install on Windows is the [Vagrant
method][install-vagrant].

## Slow internet connections

If you have a very slow network connection, however, you may want to
avoid using Vagrant (which involves downloading an Ubuntu virtual
machine or Linux Container) and either
[install directly][install-direct] (recommended), or use
[the manual install process][install-generic] instead.  These options
only support Linux.

An alternative option if you have poor network connectivity is to rent
a cloud server and install the Zulip development environment for
remote use. See the [next section][self-install-remote] for details.

## Installing remotely

The Zulip development environment works well on remote virtual
machines. This can be a good alternative for those with poor network
connectivity or who have limited storage/memory on their local
machines.

We recommend giving the Zulip development environment its **own
virtual machine**, running one of
[the supported platforms for direct installation][install-direct],
with at least **2GB of memory**.

If the Zulip development environment will be the only thing running on
the remote virtual machine, we recommend installing
[directly][install-direct]. Otherwise, we recommend the
[Vagrant][install-vagrant] method so you can easily uninstall if you
need to.

## Next steps

Once you've installed the Zulip development environment, you'll want
to read these documents to learn how to use it:

* [Using the Development Environment][using-dev-env]
* [Testing][testing] (and [Configuring CI][ci])

And if you've setup the Zulip development environment on a remote
machine, take a look at our tips for
[developing remotely][dev-remote].

[dev-remote]: remote.html
[install-direct]: ../development/setup-advanced.html#installing-directly-on-ubuntu-debian-centos-or-fedora
[install-docker]: ../development/setup-advanced.html#using-docker-experimental
[install-generic]: ../development/setup-advanced.html#installing-manually-on-linux
[install-vagrant]: ../development/setup-vagrant.html
[self-install-remote]: #installing-remotely
[self-slow-internet]: #slow-internet-connections
[configure-proxy]: ../development/setup-vagrant.html#specifying-a-proxy
[using-dev-env]: using.html
[testing]: ../testing/testing.html
[ci]: ../git/cloning.html#step-3-configure-continuous-integration-for-your-fork
