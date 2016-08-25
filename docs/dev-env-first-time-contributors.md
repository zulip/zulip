## Vagrant environment setup tutorial

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
* [Troubleshooting & Common Errors](#troubleshooting-common-errors)

If you encounter errors installing the Zulip development environment,
check [Troubleshooting & Common
Errors](#troubleshooting-common-errors). If that doesn't help, please
visit [the `provision` stream in the Zulip developers'
chat](https://zulip.tabbott.net/#narrow/stream/provision) for realtime
help, or send a note to the [Zulip-devel Google
group](https://groups.google.com/forum/#!forum/zulip-devel) or [file
an issue](https://github.com/zulip/zulip/issues).

### Requirements

Installing the Zulip dev environment requires downloading several
hundred megabytes of dependencies. You will need an active internet
connection throughout the entire installation processes. (See
[Specifying a
proxy](brief-install-vagrant-dev.html#specifying-a-proxy) if you need
a proxy to access the internet.)


- **All**: 2GB available RAM, Active broadband internet connection.
- **OS X**: OS X (El Capitan recommended, untested on previous versions), Git,
  [VirtualBox][vbox-dl], [Vagrant][vagrant-dl].
- **Ubuntu**: 14.04 64-bit or 16.04 64-bit, Git, [Vagrant][vagrant-dl], lxc.
- **Windows**: Windows 64-bit (Win 10 recommended; Win 7 untested), hardware
  virtualization enabled (VT-X or AMD-V), administrator access,
  [Cygwin][cygwin-dl], [VirtualBox][vbox-dl], [Vagrant][vagrant-dl].

Don't see your system listed above? Check out:
* [Brief installation instructions for Vagrant development
  environment](brief-install-vagrant-dev.html)
* [Installing manually on UNIX-based platforms](install-generic-unix-dev.html)

[cygwin-dl]: http://cygwin.com/

### Step 1: Install Prerequisites

Jump to:

* [OS X](#os-x)
* [Ubuntu](#ubuntu)
* [Windows](#windows-10)

#### OS X

1. Install [VirtualBox][vbox-dl]
2. Install [Vagrant][vagrant-dl]

Now you are ready for [Step 2: Get Zulip Code.](#step-2-get-zulip-code)

#### Ubuntu

The setup for Ubuntu 14.04 Trusty and Ubuntu 16.04 Xenial are the same.

If you're in a hurry, you can copy and paste the following into your terminal
after which you can jump to [Step 2: Get Zulip Code](#step-2-get-zulip-code):

```
sudo apt-get purge vagrant
wget https://releases.hashicorp.com/vagrant/1.8.4/vagrant_1.8.4_x86_64.deb
sudo dpkg -i vagrant*.deb
sudo apt-get install build-essential git ruby lxc lxc-templates cgroup-lite redir
vagrant plugin install vagrant-lxc
vagrant lxc sudoers
```

For a step-by-step explanation, read on.

##### 1. Install Vagrant

For both 14.04 Trusty and 16.04 Xenial, you'll need a more recent version of
Vagrant than what's available in the official Ubuntu repositories.

First uninstall any vagrant package you may have installed from the Ubuntu
repository:

```
christie@ubuntu-desktop:~
$ sudo apt-get purge vagrant
```

Now download and install the most recent .deb package from [Vagrant][vagrant-dl]:

```
christie@ubuntu-desktop:~
$ wget https://releases.hashicorp.com/vagrant/1.8.4/vagrant_1.8.4_x86_64.deb

christie@ubuntu-desktop:~
$ sudo dpkg -i vagrant*.deb
```

##### 2. Install remaining dependencies

Now install git and lxc-related packages:

```
christie@ubuntu-desktop:~
$ sudo apt-get install build-essential git ruby lxc lxc-templates cgroup-lite redir
```

##### 3. Install the vagrant lxc plugin:

```
christie@ubuntu-desktop:~
$ vagrant plugin install vagrant-lxc
Installing the 'vagrant-lxc' plugin. This can take a few minutes...
Installed the plugin 'vagrant-lxc (1.2.1)'!
```

If you encounter an error when trying to install the vagrant-lxc plugin, [see
this](#nomethoderror-when-installing-vagrant-lxc-plugin-ubuntu-1604).

##### 4. Configure sudo to be passwordless

Finally, [configure sudo to be passwordless when using Vagrant LXC][avoiding-sudo]:

```
christie@ubuntu-desktop:~
$ vagrant lxc sudoers
[sudo] password for christie:
```

Now you are ready for [Step 2: Get Zulip Code.](#step-2-get-zulip-code)

[vagrant-dl]: https://www.vagrantup.com/downloads.html
[vagrant-lxc]: https://github.com/fgrehm/vagrant-lxc
[vbox-dl]: https://www.virtualbox.org/wiki/Downloads
[avoiding-sudo]: https://github.com/fgrehm/vagrant-lxc#avoiding-sudo-passwords

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
- runs the `tools/provision.py` script inside the virtual machine/container, which
  downloads all required dependencies, sets up the python environment for
  the Zulip dev environment, and initializes a default test database.

You will need an active internet connection during the entire
processes. (See [Specifying a
proxy](brief-install-vagrant-dev.html#specifying-a-proxy) if you need
a proxy to access the internet.) And if you're running into any
problems, please come chat with us [in the `provision` stream of our
developers' chat](https://zulip.tabbott.net/#narrow/stream/provision).

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

As you can see above the application's root directory, where you can
execute Django's command line utilities is:

```
/srv/zulip/
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

You should see something like [(this screenshot of the Zulip dev
environment)](https://raw.githubusercontent.com/zulip/zulip/master/docs/images/zulip-dev.png).

![Image of Zulip dev environment](https://raw.githubusercontent.com/zulip/zulip/master/docs/images/zulip-dev.png)

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
re-provision your vagrant machine using `vagrant provision`
(or just `python tools/provision.py` from `/srv/zulip` inside the Vagrant
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
environment][using-dev-environment.html].

### Troubleshooting & Common Errors

Zulip's `vagrant` provisioning process logs useful debugging output to
`/var/log/zulip_provision.log`; if you encounter a new issue, please
attach a copy of that file to your bug report.

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

The `tools/provision.py` script may encounter an error related to `npm install`
that looks something like:

```
==> default: + npm install
==> default: Traceback (most recent call last):
==> default:   File "/srv/zulip/tools/provision.py", line 195, in <module>
==> default:
==> default: sys.exit(main())
==> default:   File "/srv/zulip/tools/provision.py", line 191, in main
==> default:
==> default: run(["npm", "install"])
==> default:   File "/srv/zulip/scripts/lib/zulip_tools.py", line 78, in run
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

See ["Possible testing issues"](testing.html#possible-testing-issues).
