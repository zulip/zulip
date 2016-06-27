
Installing the Zulip Development environment
============================================

* [Development environment setup for first-time
  contributors](#development-environment-setup-for-first-time-contributors)
* [Brief installation instructions for Vagrant development
  environment](#brief-installation-instructions-for-vagrant-development-environment)
* [Installing on Ubuntu 14.04 Trusty without
  Vagrant](#installing-on-ubuntu-1404-trusty-without-vagrant) (possibly more
  convenient but more work to maintain/uninstall)
* [Installing manually on UNIX-based
  platforms](#installing-manually-on-unix-based-platforms)
* [Using Docker (experimental)](#using-docker-experimental)
* [Using the Development Environment](#using-the-development-environment)
* [Running the test suite](#running-the-test-suite)
* [Possible testing issues](#possible-testing-issues)

Those who have installed Zulip before or are experienced at administering Linux
may wish to skip ahead to [Brief installation instructions for Vagrant
development environment](#brief-installation-instructions-for-vagrant-development-environment),
[Using Docker (experimental)](#using-docker-experimental), or [Installing
manually on UNIX-based platforms](#installing-manually-on-unix-based-platforms).

## Development environment setup for first-time contributors

This section guides first-time contributors through installing the Zulip dev
environment on Windows 10, OS X El Capitan, Ubuntu 14.04, and Ubuntu 16.04.

The recommended method for installing the Zulip dev environment is to use
Vagrant with VirtualBox on Windows and OS X, and Vagrant with LXC on
Ubuntu. This method creates a virtual machine (for Windows and OS X)
or a Linux container (for Ubuntu) inside which the Zulip server and
all related services will run.

Contents:
* [Requirements](#requirements)
* [Step 1: Install Prerequisites](#step-1-install-prerequisites)
* [Step 2: Get Zulip code](#step-2-get-zulip-code)
* [Step 3: Start the dev environment](#step-3-start-the-dev-environment)
* [Step 4: Developing](#step-4-developing)
* [Troubleshooting & Common Errors](#troubleshooting--common-errors)

If you encounter errors installing the Zulip dev environment and they are not addressed in [Troubleshooting & Common Errors](#troubleshooting--common-errors), send a note to the [Zulip-devel Google group](https://groups.google.com/forum/#!forum/zulip-devel) or [file an issue](https://github.com/zulip/zulip/issues).

### Requirements

Installing the Zulip dev environment requires downloading several
hundred megabytes of dependencies. You will need an active internet
connection throughout the entire installation processes. (See
[Specifying a proxy](#specifying-a-proxy) if you need a proxy to
access the internet.)


- **All**: 1.5GB available RAM, Active broadband internet connection.
- **OS X**: OS X (El Capitan recommended, untested on previous versions), Git,
  [VirtualBox][vbox-dl], [Vagrant][vagrant-dl].
- **Ubuntu**: 14.04 64-bit or 16.04 64-bit, Git, [Vagrant][vagrant-dl], lxc.
- **Windows**: Windows 64-bit (Win 10 recommended; Win 7 untested), hardware
  virtualization enabled (VT-X or AMD-V), administrator access,
  [Cygwin][cygwin-dl], [VirtualBox][vbox-dl], [Vagrant][vagrant-dl].

Don't see your system listed above? Check out:
* [Brief installation instructions for Vagrant development
  environment](#brief-installation-instructions-for-vagrant-development-environment)
* [Installing manually on UNIX-based
  platforms](#installing-manually-on-unix-based-platforms)

[cygwin-dl]: http://cygwin.com/

### Step 1: Install Prerequisites

Jump to:

* [OS X](#os-x)
* [Ubuntu 14.04 Trusty](#ubuntu-1404)
* [Ubuntu 16.04 Xenial](#ubuntu-1604)
* [Windows](#windows-10)

#### OS X

1. Install [VirtualBox][vbox-dl]
2. Install [Vagrant][vagrant-dl]

Now you are ready for [Step 2: Get Zulip Code.](#step-2-get-zulip-code)

#### Ubuntu 14.04

If you're in a hurry, you can copy and paste into your terminal after which you
can jump to [Step 2: Get Zulip Code](#step-2-get-zulip-code):

```
sudo apt-get purge vagrant
wget https://releases.hashicorp.com/vagrant/1.8.1/vagrant_1.8.1_x86_64.deb
sudo dpkg -i vagrant*.deb
sudo apt-get install git lxc lxc-templates cgroup-lite redir
vagrant plugin install vagrant-lxc
```

For a step-by-step explanation, read on.

##### 1. Install Vagrant

For 14.04 Trusty you'll need a more recent version of Vagrant than what's
available in the official Ubuntu repositories.

First uninstall any vagrant package you may have installed from the Ubuntu
repository:

```
christie@trusty-desktop:~
$ sudo apt-get purge vagrant
```

Now download and install the most recent .deb package from [Vagrant][vagrant-dl]:

```
christie@trusty-desktop:~
$ wget https://releases.hashicorp.com/vagrant/1.8.1/vagrant_1.8.1_x86_64.deb

christie@trusty-desktop:~
$ sudo dpkg -i vagrant*.deb
```


##### 2. Install remaining dependencies

Now install git and lxc-related packages:

```
christie@trusty-desktop:~
$ sudo apt-get install git lxc lxc-templates cgroup-lite redir
```

##### 3. Install the vagrant lxc plugin:

```
christie@trusty-desktop:~
$ vagrant plugin install vagrant-lxc
Installing the 'vagrant-lxc' plugin. This can take a few minutes...
Installed the plugin 'vagrant-lxc (1.2.1)'!
```

Now you are ready for [Step 2: Get Zulip Code.](#step-2-get-zulip-code)

#### Ubuntu 16.04

If you're in a hurry, you can copy and paste into your terminal after which you
can jump to [Step 2: Get Zulip Code](#step-2-get-zulip-code):

```
sudo apt-get install git vagrant lxc lxc-templates cgroup-lite redir
vagrant plugin install vagrant-lxc
vagrant lxc sudoers
```

For a step-by-step explanation, read on.

##### 1. Install git, vagrant, lxc, and related dependencies:

```
christie@xenial-desktop:~
$ sudo apt-get install git vagrant lxc lxc-templates cgroup-lite redir
```

##### 2. Install the vagrant lxc plugin:

```
christie@xenial-desktop:~
$ vagrant plugin install vagrant-lxc
Installing the 'vagrant-lxc' plugin. This can take a few minutes...
Installed the plugin 'vagrant-lxc (1.2.1)'!
```

If you encounter an error when trying to install the vagrant-lxc plugin, [see
this](#nomethoderror-when-installing-vagrant-lxc-plugin-ubuntu-1604).

##### 3. Configure sudo to be passwordless

Finally, [configure sudo to be passwordless when using Vagrant LXC][avoiding-sudo]:

```
christie@xenial-desktop:~
$ vagrant lxc sudoers
[sudo] password for christie:
```

Now you are ready for [Step 2: Get Zulip Code.](#step-2-get-zulip-code)

#### Windows 10

1. Install [Cygwin][cygwin-dl]. Make sure to install default required
   packages along with **git**, **curl**, **openssh**, and **rsync**
   binaries.
2. Install [VirtualBox][vbox-dl]
3. Install [Vagrant][vagrant-dl]

##### Configure Cygwin

In order for symlinks to work within the Ubuntu virtual machine, you must tell
Cygwin to create them as [native Windows
symlinks](https://cygwin.com/cygwin-ug-net/using.html#pathnames-symlinks). The
easiest way to do this is to add a line to `~/.bash_profile` setting the CYGWIN
environment variable.

Open a Cygwin window and do this:

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

Now you are ready for [Step 2: Get Zulip Code.](#step-2-get-zulip-code)

### Step 2: Get Zulip Code

If you haven't already created an ssh key and added it to your Github account,
you should do that now by following [these
instructions](https://help.github.com/articles/generating-an-ssh-key/).

1. In your browser, visit https://github.com/zulip/zulip and click the
   `fork` button. You will need to be logged in to Github to do this.
2. Open Terminal (OS X/Ubuntu) or Cygwin (Windows; must run as an Administrator)
3. In Terminal/Cygwin, clone your fork:
```
git clone git@github.com:YOURUSERNAME/zulip.git
```

This will create a 'zulip' directory and download the Zulip code into it.

Don't forget to replace YOURUSERNAME with your git username. You will see
something like:

```
christie@win10 ~
$ git clone git@github.com:YOURUSERNAME/zulip.git
Cloning into 'zulip'...
remote: Counting objects: 73571, done.
remote: Compressing objects: 100% (2/2), done.
remote: Total 73571 (delta 1), reused 0 (delta 0), pack-reused 73569
Receiving objects: 100% (73571/73571), 105.30 MiB | 6.46 MiB/s, done.
Resolving deltas: 100% (51448/51448), done.
Checking connectivity... done.
Checking out files: 100% (1912/1912), done.`
```

Now you are ready for [Step 3: Start the dev
environment.](#step-3-start-the-dev-environment)

### Step 3: Start the dev environment

Change into the zulip directory and tell vagrant to start the Zulip
dev environment with `vagrant up`.

```
christie@win10 ~
$ cd zulip

christie@win10 ~/zulip
$ vagrant up
```

The first time you run this command it will take some time because vagrant
does the following:

- downloads the base Ubuntu 14.04 virtual machine image (for OS X and Windows)
  or container (for Ubuntu)
- configures this virtual machine/container for use with Zulip,
- creates a shared directory mapping your clone of the Zulip code inside the
  virtual machine/container at `/srv/zulip`
- runs the `provision.py` script inside the virtual machine/container, which
  downloads all required dependencies, sets up the python environment for
  the Zulip dev environment, and initializes a default test database.

You will need an active internet connection during the entire processes. (See
[Specifying a proxy](#specifying-a-proxy) if you need a proxy to access the
internet.)

Once `vagrant up` has completed, connect to the dev environment with `vagrant
ssh`:

```
christie@win10 ~/zulip
$ vagrant ssh
```

You should see something like this on Windows and OS X:

```
Welcome to Ubuntu 14.04.4 LTS (GNU/Linux 3.13.0-85-generic x86_64)

 * Documentation:  https://help.ubuntu.com/

  System information as of Wed May  4 21:45:43 UTC 2016

  System load:  0.61              Processes:           88
  Usage of /:   3.5% of 39.34GB   Users logged in:     0
  Memory usage: 7%                IP address for eth0: 10.0.2.15
  Swap usage:   0%

  Graph this data and manage this system at:
    https://landscape.canonical.com/

  Get cloud support with Ubuntu Advantage Cloud Guest:
    http://www.ubuntu.com/business/services/cloud

0 packages can be updated.
0 updates are security updates.
```

Or something as brief as this in the case of Ubuntu:

```
Welcome to Ubuntu 14.04.1 LTS (GNU/Linux 4.4.0-21-generic x86_64)

 * Documentation:  https://help.ubuntu.com/
```

Congrats, you're now inside the Zulip dev environment!

You can confirm this by looking at the command prompt, which starts with
`(zulip-venv)`.

Next, start the Zulip server:

```
(zulip-venv)vagrant@vagrant-ubuntu-trusty-64:~ $
/srv/zulip/tools/run-dev.py --interface=''
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
navigating to [http://localhost:9991/](http://localhost:9991/) in your browser
on your main machine.

You should see something like this:

![Image of Zulip dev environment](/docs/images/zulip-dev.png)

The Zulip server will continue to run and send output to the terminal window.
When you navigate to Zulip in your browser, check your terminal and you
should see something like:

```
2016-05-04 18:21:57,547 INFO     127.0.0.1       GET     302 582ms (+start: 417ms) / (unauth via ?)
[04/May/2016 18:21:57]"GET / HTTP/1.0" 302 0
2016-05-04 18:21:57,568 INFO     127.0.0.1       GET     301   4ms /login (unauth via ?)
[04/May/2016 18:21:57]"GET /login HTTP/1.0" 301 0
2016-05-04 18:21:57,819 INFO     127.0.0.1       GET     200 209ms (db: 7ms/2q) /login/ (unauth via ?)
```

Now you're ready for [Step 4: Developing.](#step-4-developing)

### Step 4: Developing

#### Where to edit files

You'll work by editing files on your host machine, in the directory where you
cloned Zulip. Use your favorite editor (Sublime, Atom, Vim, Emacs, Notepad++,
etc.).

When you save changes they will be synced automatically to the Zulip dev environment
on the virtual machine/container.

Each component of the Zulip development server will automatically
restart itself or reload data appropriately when you make changes. So,
to see your changes, all you usually have to do is reload your
browser.  More details on how this works are available below.

Don't forget to read through the [code style
guidelines](https://zulip.readthedocs.io/en/latest/code-style.html#general) for
details about how to configure your editor for Zulip. For example, indentation
should be set to 4 spaces rather than tabs.

#### Understanding run-dev.py debugging output

It's good to have the terminal running `run-dev.py` up as you work since error
messages including tracebacks along with every backend request will be printed
there.

See [Logging](http://zulip.readthedocs.io/en/latest/logging.html) for
further details on the run-dev.py console output.

#### Committing and pushing changes with git

When you're ready to commit or push changes via git, you will do this by
running git commands in Terminal (OS X/Ubuntu) or Cygwin (Windows) in the directory
where you cloned Zulip on your main machine.

If you're new to working with Git/Github, check out [this
guide](https://help.github.com/articles/create-a-repo/#commit-your-first-change).

#### Maintaining the dev environment

If after rebasing onto a new version of the Zulip server, you receive
new errors while starting the Zulip server or running tests, this is
probably not because Zulip's master branch is broken.  Instead, this
is likely because we've recently merged changes to the development
environment provisioning process that you need to apply to your
development environmnet.  To update your environment, you'll need to
re-provision your vagrant machine using `vagrant reload --provision`
(or just `python provision.py` from `/srv/zulip` inside the Vagrant
guest); this should be pretty fast and we're working to make it faster.

See also the documentation on the [testing
page](http://zulip.readthedocs.io/en/latest/testing.html#manual-testing-local-app-web-browser)
for how to destroy and rebuild your database if you want to clear out test data.

#### Rebuilding the dev environment

If you ever want to recreate your development environment again from
scratch (e.g. to test as change you've made to the provisioning
process, or because you think something is broken), you can do so
using `vagrant destroy` and then `vagrant up`.  This will usually be
much faster than the original `vagrant up` since the base image is
already cached on your machine (it takes about 5 minutes to run with a
fast Internet connection).

#### Shutting down the dev environment for use later

To shut down but preserve the dev environment so you can use it again
later use `vagrant halt` or `vagrant suspend`.

You can do this from the same Terminal/Cygwin window that is running
run-dev.py by pressing ^C to halt the server and then typing `exit`. Or you
can halt vagrant from another Terminal/Cygwin window.

From the window where run-dev.py is running:

```
2016-05-04 18:33:13,330 INFO     127.0.0.1       GET     200  92ms /register/ (unauth via ?)
^C
KeyboardInterrupt
(zulip-venv)vagrant@vagrant-ubuntu-trusty-64:/srv/zulip$ exit
logout
Connection to 127.0.0.1 closed.
christie@win10 ~/zulip
```
Now you can suspend the dev environment:

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

#### Resuming the dev environment

When you're ready to work on Zulip again, run `vagrant up`. You will also need
to connect to the virtual machine with `vagrant ssh` and re-start the Zulip
server:

```
christie@win10 ~/zulip
$ vagrant up
$ vagrant ssh
/srv/zulip/tools/run-dev.py --interface=''
```

#### Next Steps

At this point you should [read about using the development
environment][using-dev].

### Troubleshooting & Common Errors

#### The box 'ubuntu/trusty64' could not be found (Windows/Cygwin)

If you see the following error when you run `vagrant up` on Windows:

```
The box 'ubuntu/trusty64' could not be found or
could not be accessed in the remote catalog. If this is a private
box on HashiCorp's Atlas, please verify you're logged in via
`vagrant login`. Also, please double-check the name. The expanded
URL and error message are shown below:
URL: ["https://atlas.hashicorp.com/ubuntu/trusty64"]
```

Then the version of curl that ships with Vagrant is not working on your
machine. The fix is simple: replace it with the version from Cygwin.

First, determine the location of Cygwin's curl with `which curl`:

```
christie@win10 ~/zulip
$ which curl
/usr/bin/curl
```
Now determine the location of Vagrant with `which vagrant`:
```
christie@win10 ~/zulip
$ which vagrant
/cygdrive/c/HashiCorp/Vagrant/bin/vagrant
```
The path **up until `/bin/vagrant`** is what you need to know. In the example above it's `/cygdrive/c/HashiCorp/Vagrant`.

Finally, copy Cygwin's curl to Vagrant `embedded/bin` directory:
```
christie@win10 ~/zulip
$ cp /usr/bin/curl.exe /cygdrive/c/HashiCorp/Vagrant/embedded/bin/
```

Now re-run `vagrant up` and vagrant should be able to fetch the required
box file.

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

First, if you are using Windows, **make sure you have run Cygwin as an
administrator**. By default, only administrators can create symbolic links on
Windows.

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
symbolic links by running this command in Terminal/Cygwin:

```
vboxmanage setextradata YOURVMNAME VBoxInternal2/SharedFoldersEnableSymlinksCreate/srv_zulip 1
```

The virtual machine needs to be shut down when you run this command.

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
this post](http://stackoverflow.com/questions/22575261/vagrant-stuck-connection-timeout-retrying#22575302).

#### npm install error

The `provision.py` script may encounter an error related to `npm install`
that looks something like:

```
==> default: + npm install
==> default: Traceback (most recent call last):
==> default:   File "/srv/zulip/provision.py", line 195, in <module>
==> default:
==> default: sys.exit(main())
==> default:   File "/srv/zulip/provision.py", line 191, in main
==> default:
==> default: run(["npm", "install"])
==> default:   File "/srv/zulip/zulip_tools.py", line 78, in run
==> default:
==> default: raise subprocess.CalledProcessError(rc, args)
==> default: subprocess
==> default: .
==> default: CalledProcessError
==> default: :
==> default: Command '['npm', 'install']' returned non-zero exit status 34
The SSH command responded with a non-zero exit status. Vagrant
assumes that this means the command failed. The output for this command
should be in the log above. Please read the output to determine what
went wrong.
```

Usually this error is not fatal. Try connecting to the dev environment and
re-trying the command from withing the virtual machine:

```
christie@win10 ~/zulip
$ vagrant ssh
(zulip-venv)vagrant@vagrant-ubuntu-trusty-64:~
$ cd /srv/zulip
(zulip-venv)vagrant@vagrant-ubuntu-trusty-64:/srv/zulip
$ npm install
npm WARN optional Skipping failed optional dependency /chokidar/fsevents:
npm WARN notsup Not compatible with your operating system or architecture: fsevents@1.0.12
```

These are just warnings so it is okay to proceed and start the Zulip server.

#### NoMethodError when installing vagrant-lxc plugin (Ubuntu 16.04)

If you see the following error when you try to install the vagrant-lxc plugin:

```
/usr/lib/ruby/2.3.0/rubygems/specification.rb:946:in `all=': undefined method `group_by' for nil:NilClass (NoMethodError)
  from /usr/lib/ruby/vendor_ruby/vagrant/bundler.rb:275:in `with_isolated_gem'
  from /usr/lib/ruby/vendor_ruby/vagrant/bundler.rb:231:in `internal_install'
  from /usr/lib/ruby/vendor_ruby/vagrant/bundler.rb:102:in `install'
  from /usr/lib/ruby/vendor_ruby/vagrant/plugin/manager.rb:62:in `block in install_plugin'
  from /usr/lib/ruby/vendor_ruby/vagrant/plugin/manager.rb:72:in `install_plugin'
  from /usr/share/vagrant/plugins/commands/plugin/action/install_gem.rb:37:in `call'
  from /usr/lib/ruby/vendor_ruby/vagrant/action/warden.rb:34:in `call'
  from /usr/lib/ruby/vendor_ruby/vagrant/action/builder.rb:116:in `call'
  from /usr/lib/ruby/vendor_ruby/vagrant/action/runner.rb:66:in `block in run'
  from /usr/lib/ruby/vendor_ruby/vagrant/util/busy.rb:19:in `busy'
  from /usr/lib/ruby/vendor_ruby/vagrant/action/runner.rb:66:in `run'
  from /usr/share/vagrant/plugins/commands/plugin/command/base.rb:14:in `action'
  from /usr/share/vagrant/plugins/commands/plugin/command/install.rb:32:in `block in execute'
  from /usr/share/vagrant/plugins/commands/plugin/command/install.rb:31:in `each'
  from /usr/share/vagrant/plugins/commands/plugin/command/install.rb:31:in `execute'
  from /usr/share/vagrant/plugins/commands/plugin/command/root.rb:56:in `execute'
  from /usr/lib/ruby/vendor_ruby/vagrant/cli.rb:42:in `execute'
  from /usr/lib/ruby/vendor_ruby/vagrant/environment.rb:268:in `cli'
  from /usr/bin/vagrant:173:in `<main>'
```

And you have vagrant version 1.8.1, then you need to patch vagrant manually.
See [this post](https://github.com/mitchellh/vagrant/issues/7073) for an
explanation of the issue, which should be fixed when Vagrant 1.8.2 is released.

In the meantime, read [this
post](http://stackoverflow.com/questions/36811863/cant-install-vagrant-plugins-in-ubuntu-16-04/36991648#36991648)
for how to create and apply the patch.

It will look something like this:

```
christie@xenial:~
$ sudo patch --directory /usr/lib/ruby/vendor_ruby/vagrant < vagrant-plugin.patch
patching file bundler.rb
```

#### Permissions errors when running the test suite in LXC

When building the development environment using Vagrant and the LXC provider,
if you encounter permissions errors, you may need to `chown -R 1000:$(whoami)
/path/to/zulip` on the host before running `vagrant up` in order to ensure that
the synced directory has the correct owner during provision. This issue will
arise if you run `id username` on the host where `username` is the user running
Vagrant and the output is anything but 1000.

This seems to be caused by Vagrant behavior; for more information, see [the
vagrant-lxc FAQ entry about shared folder permissions ][lxc-sf].

Brief installation instructions for Vagrant development environment
-------------

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

[using-dev]: #using-the-development-environment

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

Installing on Ubuntu 14.04 Trusty without Vagrant
----------------------------------
Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

If you'd like to install a Zulip development environment on a server
that's already running Ubuntu 14.04 Trusty, you can do that by just
running:

```
sudo apt-get update
python /srv/zulip/provision.py

cd /srv/zulip
source /srv/zulip-venv/bin/activate
./tools/run-dev.py
```

Note that there is no supported uninstallation process without Vagrant
(with Vagrant, you can just do `vagrant destroy` to clean up the
development environment).

Installing manually on UNIX-based platforms
-------

* [Debian or Ubuntu systems](#on-debian-or-ubuntu-systems)
* [Fedora 22 (experimental)](#on-fedora-22-experimental)
* [CentOS 7 Core (experimental)](#on-centos-7-core-experimental)
* [OpenBSD 5.8 (experimental)](#on-openbsd-58-experimental)
* [Fedora/CentOS](#common-to-fedoracentos-instructions)
* [Steps for all systems](#all-systems)

If you really want to install everything manually, the below instructions
should work.

Install the following non-Python dependencies:
 * libffi-dev — needed for some Python extensions
 * postgresql 9.1 or later — our database (client, server, headers)
 * nodejs 0.10 (and npm)
 * memcached (and headers)
 * rabbitmq-server
 * libldap2-dev
 * python-dev
 * redis-server — rate limiting
 * tsearch-extras — better text search
 * libfreetype6-dev — needed before you pip install Pillow to properly generate emoji PNGs

### On Debian or Ubuntu systems:

#### Using the official Ubuntu repositories and `tsearch-extras` deb package:

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
sudo apt-get install closure-compiler libfreetype6-dev libffi-dev \
    memcached rabbitmq-server libldap2-dev redis-server \
    postgresql-server-dev-all libmemcached-dev python-dev \
    hunspell-en-us nodejs nodejs-legacy npm git yui-compressor \
    puppet gettext

# If on 12.04 or wheezy:
sudo apt-get install postgresql-9.1
wget https://dl.dropboxusercontent.com/u/283158365/zuliposs/postgresql-9.1-tsearch-extras_0.1.2_amd64.deb
sudo dpkg -i postgresql-9.1-tsearch-extras_0.1.2_amd64.deb

# If on 14.04:
sudo apt-get install postgresql-9.3
wget https://dl.dropboxusercontent.com/u/283158365/zuliposs/postgresql-9.3-tsearch-extras_0.1.2_amd64.deb
sudo dpkg -i postgresql-9.3-tsearch-extras_0.1.2_amd64.deb

# If on 15.04 or jessie:
sudo apt-get install postgresql-9.4
wget https://dl.dropboxusercontent.com/u/283158365/zuliposs/postgresql-9.4-tsearch-extras_0.1_amd64.deb
sudo dpkg -i postgresql-9.4-tsearch-extras_0.1_amd64.deb
```

Now continue with the [All Systems](#all-systems) instructions below.

#### Using the [official Zulip PPA](https://launchpad.net/~tabbott/+archive/ubuntu/zulip/+packages) (for 14.04 Trusty):

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
sudo add-apt-repository ppa:tabbott/zulip
sudo apt-get update
sudo apt-get install closure-compiler libfreetype6-dev libffi-dev \
    memcached rabbitmq-server libldap2-dev redis-server \
    postgresql-server-dev-all libmemcached-dev python-dev \
    hunspell-en-us nodejs nodejs-legacy npm git yui-compressor \
    puppet gettext tsearch-extras
```

Now continue with the [All Systems](#all-systems) instructions below.

### On Fedora 22 (experimental):

These instructions are experimental and may have bugs; patches
welcome!

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
sudo dnf install libffi-devel memcached rabbitmq-server \
    openldap-devel python-devel redis postgresql-server \
    postgresql-devel postgresql libmemcached-devel freetype-devel \
    nodejs npm yuicompressor closure-compiler gettext
```

Finally continue with the [All Systems](#all-systems) instructions below.

### On CentOS 7 Core (experimental):

These instructions are experimental and may have bugs; patches
welcome!

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
# Add user zulip to the system (not necessary if you configured zulip
# as the administrator user during the install process of CentOS 7).
useradd zulip

# Create a password for zulip user
passwd zulip

# Allow zulip to sudo
visudo
# Add this line after line `root    ALL=(ALL)       ALL`
zulip   ALL=(ALL)       ALL

# Switch to zulip user
su zulip

# Enable EPEL 7 repo so we can install rabbitmq-server, redis and
# other dependencies
sudo yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm

# Install dependencies
sudo yum install libffi-devel memcached rabbitmq-server openldap-devel \
    python-devel redis postgresql-server postgresql-devel postgresql \
    libmemcached-devel wget python-pip openssl-devel freetype-devel \
    libjpeg-turbo-devel zlib-devel nodejs yuicompressor \
    closure-compiler gettext

# We need these packages to compile tsearch-extras
sudo yum groupinstall "Development Tools"

# clone Zulip's git repo and cd into it
cd && git clone https://github.com/zulip/zulip && cd zulip/

## NEEDS TESTING: The next few DB setup items may not be required at all.
# Initialize the postgres db
sudo postgresql-setup initdb

# Edit the postgres settings:
sudo vi /var/lib/pgsql/data/pg_hba.conf

# Change these lines:
host    all             all             127.0.0.1/32            ident
host    all             all             ::1/128                 ident
# to this:
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
```

Now continue with the [Common to Fedora/CentOS](#common-to-fedoracentos-instructions) instructions below.

### On OpenBSD 5.8 (experimental):

These instructions are experimental and may have bugs; patches
welcome!

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
doas pkg_add sudo bash gcc postgresql-server redis rabbitmq \
    memcached node libmemcached py-Pillow py-cryptography py-cffi

# Get tsearch_extras and build it (using a modified version which
# aliases int4 on OpenBSD):
git clone https://github.com/blablacio/tsearch_extras
cd tsearch_extras
gmake && sudo gmake install

# Point environment to custom include locations and use newer GCC
# (needed for Node modules):
export CFLAGS="-I/usr/local/include -I/usr/local/include/sasl"
export CXX=eg++

# Create tsearch_data directory:
sudo mkdir /usr/local/share/postgresql/tsearch_data


# Hack around missing dictionary files -- need to fix this to get the
# proper dictionaries from what in debian is the hunspell-en-us
# package.
sudo touch /usr/local/share/postgresql/tsearch_data/english.stop
sudo touch /usr/local/share/postgresql/tsearch_data/en_us.dict
sudo touch /usr/local/share/postgresql/tsearch_data/en_us.affix
```

Finally continue with the [All Systems](#all-systems) instructions below.

### Common to Fedora/CentOS instructions

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
# Build and install postgres tsearch-extras module
wget https://launchpad.net/~tabbott/+archive/ubuntu/zulip/+files/tsearch-extras_0.1.3.tar.gz
tar xvzf tsearch-extras_0.1.3.tar.gz
cd ts2
make
sudo make install

# Hack around missing dictionary files -- need to fix this to get the
# proper dictionaries from what in debian is the hunspell-en-us
# package.
sudo touch /usr/share/pgsql/tsearch_data/english.stop
sudo touch /usr/share/pgsql/tsearch_data/en_us.dict
sudo touch /usr/share/pgsql/tsearch_data/en_us.affix

# Edit the postgres settings:
sudo vi /var/lib/pgsql/data/pg_hba.conf

# Add this line before the first uncommented line to enable password
# auth:
host    all             all             127.0.0.1/32            md5

# Start the services
sudo systemctl start redis memcached rabbitmq-server postgresql

# Enable automatic service startup after the system startup
sudo systemctl enable redis rabbitmq-server memcached postgresql
```

Finally continue with the [All Systems](#all-systems) instructions below.

### All Systems:

Make sure you have followed the steps specific for your platform:

* [Debian or Ubuntu systems](#on-debian-or-ubuntu-systems)
* [Fedora 22 (experimental)](#on-fedora-22-experimental)
* [CentOS 7 Core (experimental)](#on-centos-7-core-experimental)
* [OpenBSD 5.8 (experimental)](#on-openbsd-58-experimental)
* [Fedora/CentOS](#common-to-fedoracentos-instructions)

For managing Zulip's python dependencies, we recommend using a
[virtualenv](https://virtualenv.pypa.io/en/stable/).

Once you have created and activated a virtualenv, do the following:

```
pip install --upgrade pip # upgrade pip itself because older versions have known issues.
pip install --no-deps -r requirements/dev.txt # install python packages required for development
./tools/setup/install-phantomjs
./tools/install-mypy
./tools/setup/download-zxcvbn
./tools/emoji_dump/build_emoji
./scripts/setup/generate_secrets.py -d
if [ $(uname) = "OpenBSD" ]; then sudo cp ./puppet/zulip/files/postgresql/zulip_english.stop /var/postgresql/tsearch_data/; else sudo cp ./puppet/zulip/files/postgresql/zulip_english.stop /usr/share/postgresql/9.3/tsearch_data/; fi
./scripts/setup/configure-rabbitmq
./tools/setup/postgres-init-dev-db
./tools/do-destroy-rebuild-database
./tools/setup/postgres-init-test-db
./tools/do-destroy-rebuild-test-database
./manage.py compilemessages
npm install
```

If `npm install` fails, the issue may be that you need a newer version
of `npm`.  You can use `npm install -g npm` to update your version of
`npm` and try again.

To start the development server:

```
./tools/run-dev.py
```

… and visit [http://localhost:9991/](http://localhost:9991/).

#### Proxy setup for by-hand installation

If you are building the development environment on a network where a
proxy is required to access the Internet, you will need to set the
proxy in the environment as follows:

- On Ubuntu, set the proxy environment variables using:
 ```
 export https_proxy=http://proxy_host:port
 export http_proxy=http://proxy_host:port
 ```

- And set the npm proxy and https-proxy using:
 ```
 npm config set proxy http://proxy_host:port
 npm config set https-proxy http://proxy_host:port
 ```

Using Docker (experimental)
---------------------------
Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

The docker instructions for development are experimental, so they may
have bugs.  If you try them and run into any issues, please report
them!

You can also use Docker to run a Zulip development environment.
First, you need to install Docker in your development machine
following the [instructions][docker-install].  Some other interesting
links for somebody new in Docker are:

* [Get Started](https://docs.docker.com/engine/installation/linux/)
* [Understand the architecture](https://docs.docker.com/engine/understanding-docker/)
* [Docker run reference](https://docs.docker.com/engine/reference/run/)
* [Dockerfile reference](https://docs.docker.com/engine/reference/builder/)

[docker-install]: https://docs.docker.com/engine/installation/

Then you should create the Docker image based on Ubuntu Linux, first
go to the directory with the Zulip source code:

```
docker build -t user/zulipdev .
```

Now you're going to install Zulip dependencies in the image:

```
docker run -itv $(pwd):/srv/zulip -p 9991:9991 user/zulipdev /bin/bash
$ /usr/bin/python /srv/zulip/provision.py --docker
docker ps -af ancestor=user/zulipdev
docker commit -m "Zulip installed" <container id> user/zulipdev:v2
```

Finally you can run the docker server with:

```
docker run -itv $(pwd):/srv/zulip -p 9991:9991 user/zulipdev:v2 \
    /srv/zulip/tools/start-dockers
```

If you want to connect to the Docker instance to build a release
tarball you can use:

```
docker ps
docker exec -it <container id> /bin/bash
$ source /home/zulip/.bash_profile
$ <Your commands>
$ exit
```

To stop the server use:
```
docker ps
docker kill <container id>
```

If you want to run all the tests you need to start the servers first,
you can do it with:

```
docker run -itv $(pwd):/srv/zulip user/zulipdev:v2 /bin/bash
$ tools/test-all-docker
```

You can modify the source code in your development machine and review
the results in your browser.


Using the Development Environment
=================================

Once the development environment is running, you can visit
<http://localhost:9991/> in your browser.  By default, the development
server homepage just shows a list of the users that exist on the
server and you can login as any of them by just clicking on a user.
This setup saves time for the common case where you want to test
something other than the login process; to test the login process
you'll want to change `AUTHENTICATION_BACKENDS` in the not-PRODUCTION
case of `zproject/settings.py` from zproject.backends.DevAuthBackend
to use the auth method(s) you'd like to test.

While developing, it's helpful to watch the `run-dev.py` console
output, which will show any errors your Zulip development server
encounters.

When you make a change, here's a guide for what you need to do in
order to see your change take effect in Development:

* If you change Javascript, CSS, or Jinja2 backend templates (under
`templates/`), you'll just need to reload the browser window to see
changes take effect.  The Handlebars frontend HTML templates
(`static/templates`) are automatically recompiled by the
`tools/compile-handlebars-templates` job, which runs as part of
`tools/run-dev.py`.

* If you change Python code used by the the main Django/Tornado server
processes, these services are run on top of Django's [manage.py
runserver][django-runserver] which will automatically restart the
Zulip Django and Tornado servers whenever you save changes to Python
code.  You can watch this happen in the `run-dev.py` console to make
sure the backend has reloaded.

* The Python queue workers will also automatically restart when you
save changes.  However, you may need to ctrl-C and then restart
`run-dev.py` manually if a queue worker has crashed.

* If you change the database schema, you'll need to use the standard
Django migrations process to create and then run your migrations; see
the [new feature tutorial][new-feature-tutorial] for an example.
Additionally you should check out the [detailed testing
docs][testing-docs] for how to run the tests properly after doing a
migration.

(In production, everything runs under supervisord and thus will
restart if it crashes, and `upgrade-zulip` will take care of running
migrations and then cleanly restaring the server for you).

[django-runserver]: https://docs.djangoproject.com/en/1.8/ref/django-admin/#runserver-port-or-address-port
[new-feature-tutorial]: http://zulip.readthedocs.io/en/latest/new-feature-tutorial.html
[testing-docs]: http://zulip.readthedocs.io/en/latest/testing.html

Running the test suite
======================

Zulip tests must be run inside a Zulip development environment; if
you're using Vagrant, you will need to enter the Vagrant environment
before running the tests:

```
vagrant ssh
cd /srv/zulip
```

To run all the tests, do this:
```
./tools/test-all
```

For more details on how to run a single test, efficiently debug test
failures, or write tests, check out the [detailed testing
docs][tdocs].

[tdocs]: http://zulip.readthedocs.io/en/latest/testing.html



This runs the linter (`tools/lint-all`) plus all of our test suites;
they can all be run separately (just read `tools/test-all` to see
them).  You can also run individual tests which can save you a lot of
time debugging a test failure, e.g.:

```
./tools/lint-all # Runs all the linters in parallel
./tools/test-backend zerver.tests.test_bugdown.BugdownTest.test_inline_youtube
./tools/test-js-with-casper 09-navigation.js
./tools/test-js-with-node # Runs all node tests but is very fast
```

The above setup instructions include the first-time setup of test
databases, but you may need to rebuild the test database occasionally
if you're working on new database migrations.  To do this, run:

```
./tools/do-destroy-rebuild-test-database
```

Possible testing issues
=======================

- When running the test suite, if you get an error like this:

  ```
      sqlalchemy.exc.ProgrammingError: (ProgrammingError) function ts_match_locs_array(unknown, text, tsquery) does not   exist
      LINE 2: ...ECT message_id, flags, subject, rendered_content, ts_match_l...
                                                                   ^
  ```

  … then you need to install tsearch-extras, described
  above. Afterwards, re-run the `init*-db` and the
  `do-destroy-rebuild*-database` scripts.

- When building the development environment using Vagrant and the LXC
  provider, if you encounter permissions errors, you may need to
  `chown -R 1000:$(whoami) /path/to/zulip` on the host before running
  `vagrant up` in order to ensure that the synced directory has the
  correct owner during provision. This issue will arise if you run `id
  username` on the host where `username` is the user running Vagrant
  and the output is anything but 1000.
  This seems to be caused by Vagrant behavior; for more information,
  see [the vagrant-lxc FAQ entry about shared folder permissions
  ][lxc-sf].

[lxc-sf]: https://github.com/fgrehm/vagrant-lxc/wiki/FAQ#help-my-shared-folders-have-the-wrong-owner)
