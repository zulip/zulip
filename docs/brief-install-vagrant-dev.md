# Vagrant environment setup (in brief)

Start by cloning this repository: `git clone https://github.com/zulip/zulip.git`

This is the recommended approach for all platforms, and will install
the Zulip development environment inside a VM or container and works
on any platform that supports Vagrant.

The best performing way to run the Zulip development environment is
using an LXC container on a Linux host, but we support other platforms
such as Mac via Virtualbox (but everything will be 2-3x slower).

* If your host is Ubuntu 15.04 or newer, you can install and configure
  the LXC Vagrant provider directly using apt:
  ```
  sudo apt-get install vagrant lxc lxc-templates cgroup-lite redir
  vagrant plugin install vagrant-lxc
  ```
  You may want to [configure sudo to be passwordless when using Vagrant LXC][avoiding-sudo].

* If your host is Ubuntu 14.04, you will need to [download a newer
  version of Vagrant][vagrant-dl], and then do the following:
  ```
  sudo apt-get install lxc lxc-templates cgroup-lite redir
  sudo dpkg -i vagrant*.deb # in directory where you downloaded vagrant
  vagrant plugin install vagrant-lxc
  ```
  You may want to [configure sudo to be passwordless when using Vagrant LXC][avoiding-sudo].

* For other Linux hosts with a kernel above 3.12, [follow the Vagrant
  LXC installation instructions][vagrant-lxc] to get Vagrant with LXC
  for your platform.

* If your host is OS X or older Linux, [download VirtualBox][vbox-dl],
  [download Vagrant][vagrant-dl], and install them both.

* If you're on OS X and have VMWare, it should be possible to patch
  Vagrantfile to use the VMWare vagrant provider which should perform
  much better than Virtualbox.  Patches to do this by default if
  VMWare is available are welcome!

* On Windows: You can use Vagrant and Virtualbox/VMWare on Windows
  with Cygwin, similar to the Mac setup.  Be sure to create your git
  clone using `git clone https://github.com/zulip/zulip.git -c
  core.autocrlf=false` to avoid Windows line endings being added to
  files (this causes weird errors).

[vagrant-dl]: https://www.vagrantup.com/downloads.html
[vagrant-lxc]: https://github.com/fgrehm/vagrant-lxc
[vbox-dl]: https://www.virtualbox.org/wiki/Downloads
[avoiding-sudo]: https://github.com/fgrehm/vagrant-lxc#avoiding-sudo-passwords

Once that's done, simply change to your zulip directory and run
`vagrant up` in your terminal to install the development server.  This
will take a long time on the first run because Vagrant needs to
download the Ubuntu Trusty base image, but later you can run `vagrant
destroy` and then `vagrant up` again to rebuild the environment and it
will be much faster.

Once that finishes, you can run the development server as follows:

```
vagrant ssh
# Now inside the container
/srv/zulip/tools/run-dev.py --interface=''
```

To get shell access to the virtual machine running the server to run
lint, management commands, etc., use `vagrant ssh`.

(A small note on tools/run-dev.py: the `--interface=''` option will
make the development server listen on all network interfaces.  While
this is correct for the Vagrant guest sitting behind a NAT, you
probably don't want to use that option when using run-dev.py in other
environments).

At this point you should [read about using the development
environment][using-dev].

[using-dev]: using-dev-environment.html

### Specifying a proxy

If you need to use a proxy server to access the Internet, you will
need to specify the proxy settings before running `Vagrant up`.
First, install the Vagrant plugin `vagrant-proxyconf`:

```
vagrant plugin install vagrant-proxyconf.
```

Then create `~/.zulip-vagrant-config` and add the following lines to
it (with the appropriate values in it for your proxy):

```
HTTP_PROXY http://proxy_host:port
HTTPS_PROXY http://proxy_host:port
NO_PROXY localhost,127.0.0.1,.example.com
```

Now run `vagrant up` in your terminal to install the development
server. If you ran `vagrant up` before and failed, you'll need to run
`vagrant destroy` first to clean up the failed installation.

You can also change the port on the host machine that Vagrant uses by
adding to your `~/.zulip-vagrant-config` file.  E.g. if you set:

```
HOST_PORT 9971
```

(and halt and restart the Vagrant guest), then you would visit
http://localhost:9971/ to connect to your development server.
