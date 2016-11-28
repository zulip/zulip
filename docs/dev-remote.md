# Developing on a remote machine

The Zulip developer environment works well on remote virtual machines. This can
be a good alternative for those with poor network connectivity or who have
limited storage/memory on their local machines.

We recommend giving Zulip dev its own virtual machine, running Ubuntu 14.04 or
16.04, with at least 2GB of memory. If Zulip dev will be the only thing running
on the remote virtual machine, we recommend installing
[directly][install-direct]. Otherwise, we recommend the
[Vagrant][install-vagrant] method so you can easily uninstall if you need to.

## Connecting to the remote environment

Set up your remote server and connect to it using SSH or Mosh.
We recommend using [Mosh](https://mosh.org/) as it is more reliable over slow
network connections.

## Setting up the development environment

After you have connected to your remote server, you need to install the
development environment.

If Zulip dev will be the only thing running on the remote virtual machine, we
recommend installing [directly][install-direct]. Otherwise, we recommend the
[Vagrant][install-vagrant] method so you can easily uninstall if you need to.

## Running the development server

Once you have set up the development environment, you can start up the development instance of zulip with the command

```
./tools/run-dev.py
```

This will start up zulip on port 9991. You can then navigate to http://<REMOTE_IP>:9991 and you should see something like
[(this screenshot of the Zulip dev environment)](https://raw.githubusercontent.com/zulip/zulip/master/docs/images/zulip-dev.png).

![Image of Zulip dev environment](https://raw.githubusercontent.com/zulip/zulip/master/docs/images/zulip-dev.png)

You can [port forward](https://help.ubuntu.com/community/SSH/OpenSSH/PortForwarding)
using ssh instead of running the dev env on an exposed interface.

For more information, see [Using the development environment](using-dev-environment.html).

## Editing code on the remote machine

You will need to either edit code locally on your computer and sync it to the remote
development environment or just edit the zulip code base on the remote host.

#### Editing locally

If you want to edit code locally you can install your favorite text editor:
* [atom](https://atom.io/)
* [emacs](https://www.gnu.org/software/emacs/)
* [vim](http://www.vim.org/)
* [spacemacs](https://github.com/syl20bnr/spacemacs)
* [sublime](https://www.sublimetext.com/)
* etc

Next, [set up git](git-guide.html) on your local machine and clone the zulip
repository.

Once you have your code locally you will need to sync your changes to your development server:
* [Unison](https://github.com/bcpierce00/unison) Recommended
* [Rsync](https://www.digitalocean.com/community/tutorials/how-to-use-rsync-to-sync-local-and-remote-directories-on-a-vps)

#### Editing remotely

You will need to use a text editor on the remote machine:
* [emacs](https://www.gnu.org/software/emacs/)
* [vim](http://www.vim.org/)
* [spacemacs](https://github.com/syl20bnr/spacemacs)

Once you install an editor
[setup an ssh key](https://help.github.com/articles/generating-an-ssh-key/)
on your host and [clone](git-guide.html) the zulip repository.

#### Next steps

At this point you should
[read about developing](dev-env-first-time-contributors.html#step-4-developing)
and [read about using the development environment](using-dev-environment.html).

[install-direct]: dev-setup-non-vagrant.html#installing-directly-on-ubuntu
[install-generic]: dev-setup-non-vagrant.html#installing-manually-on-linux
[install-vagrant]: dev-env-first-time-contributors.html
