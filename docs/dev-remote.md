# Development on a Remote Machine

Zulip can be developed on a remote machine.
We recommend doing this if you are running Windows or have other
blockers stopping you from [developing locally](dev-overview.html).

We recommend a remote Ubuntu machine for ease of development.

## Connecting to the Remote Environment

Set up your remote server and connect to it using SSH or Mosh.
We recommend using [Mosh](https://mosh.org/) as it is more reliable over slow network connections. 

## Setting Up the Development Environment

Install the development environment on your remote server.
Follow the platform specific instructions for your specific remote instance:

* [Installing on Ubuntu](install-ubuntu-without-vagrant-dev.html).
  This offers the most convenient developer experience, if you are developing on a clean remote machine we recomend this.
* [Detailed tutorial for Vagrant development environment](dev-env-first-time-contributors.html)
* [Brief installation instructions for Vagrant development environment](brief-install-vagrant-dev.html)

## Running the Development Server

You can start up the development instance of zulip with the command

```
./tools/run-dev.py
```

This will start up zulip on port 9991. You can then navigate to http://<REMOTE_IP>:9991 and you should see something like
[(this screenshot of the Zulip dev environment)](https://raw.githubusercontent.com/zulip/zulip/master/docs/images/zulip-dev.png).

![Image of Zulip dev environment](https://raw.githubusercontent.com/zulip/zulip/master/docs/images/zulip-dev.png)

You can [port forward](https://help.ubuntu.com/community/SSH/OpenSSH/PortForwarding)
using ssh instead of running the dev env on an exposed interface.

For more information, see [Using the Development Environment](using-dev-environment.html).

## Editing Code on the Remote Machine

You will need to either edit code locally on your computer and sync it to the remote
development environment or just edit the zulip code base on the remote host.

#### Editing Locally

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

#### Editing Remotely

You will need to use a text editor on the remote machine:
* [emacs](https://www.gnu.org/software/emacs/)
* [vim](http://www.vim.org/)
* [spacemacs](https://github.com/syl20bnr/spacemacs)

Once you install an editor
[setup an ssh key](https://help.github.com/articles/generating-an-ssh-key/)
on your host and [clone](git-guide.html) the zulip repository.

#### Next Steps

At this point you should
[read about developing](dev-env-first-time-contributors.html#step-4-developing)
and [read about using the development environment](using-dev-environment.html).
