# Development environment installation

Zulip support a wide range of ways to install the Zulip development
environment. Zulip itself is built and deployed on Linux/Ubuntu. If
you have access to Ubuntu in your current setup, then you will enjoy
extra speed in your development environment.  For folks on most other
operating systems, you can be rest assured that plenty of Zulip
contributors run Ubuntu via VMs (virtual machines) on their
platforms of choice, and we are comfortable supporting developers
in many environments.

The most well supported development enviroment for Zulip is Linux.
We use Linux in production, so if you develop in Linux, you are most closely
simulating our production environment.  If you are running Linux
natively, you can either install Zulip directly or inside a container.

The second most supported operating system to develop Zulip on is
OSX. Zulip was originally mostly developed natively on OSX.  Now
most Zulip developers who use OSX run Ubuntu in a VM on OSX.
We have a fair amount of expertise with this platform.

If you use something other than Linux or OSX, such
as Windows, you may have more challenges if you run into OS-specific
issues.  We will try to help you on the public Zulip instance.  Also,
we are constantly striving to support Windows and other platforms better.

If you are not on Linux, we recommend using a VM.  Even if you are
on Linux, we recommend using a container/VM type of solution. 
The best way to get support from the Zulip community is to
use the Vagrant development environment.  It is fairly easy to 
set up and install, and many of our current developers use it, so
your peers can help you with any issues.

If you have a very slow network connection, however, you may want to
avoid using Vagrant (which involves downloading an Ubuntu image) and
either [install directly](install-ubuntu-without-vagrant-dev.html) or
use [the manual install process](install-generic-unix-dev.html)
instead.  Note that those options only support Linux.

An alternative option with poor network connectivity is to rent a
cloud server (with at least 2GB of RAM), install the development
environment there (we'd recommend the
[install directly](install-ubuntu-without-vagrant-dev.html) approach),
and connect to the development environment over SSH.

#### For LINUX/ Other UNIX Platforms

* [Detailed tutorial for Vagrant development environment](dev-env-first-time-contributors.html).  Recommended for first-time contributors.
* [Brief installation instructions for Vagrant development environment](brief-install-vagrant-dev.html)
* [Installing on Ubuntu 14.04 Trusty or 16.04 Xenial directly](install-ubuntu-without-vagrant-dev.html).
  This offers the most convenient developer experience, but is difficult to uninstall.
* [Installing manually on other UNIX platforms](install-generic-unix-dev.html)
* [Using Docker (experimental)](install-docker-dev.html)

#### For OS X

* [Detailed tutorial for Vagrant development environment](dev-env-first-time-contributors.html).  Recommended for first-time contributors.
* [Brief installation instructions for Vagrant development environment](brief-install-vagrant-dev.html)
* [Using Docker (experimental)](install-docker-dev.html)

#### For Windows

* [Detailed tutorial for Vagrant development environment](dev-env-first-time-contributors.html).  Recommended for first-time contributors.
* [Brief installation instructions for Vagrant development environment](brief-install-vagrant-dev.html)

## Using the Development Environment & Testing

Once you've installed the Zulip development environment, you'll want
to read these documents to learn how to use it:

* [Using the Development Environment](using-dev-environment.html)
* [Testing](testing.html)

