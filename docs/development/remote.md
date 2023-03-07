# Developing on a remote machine

The Zulip developer environment works well on remote virtual machines. This can
be a good alternative for those with poor network connectivity or who have
limited storage/memory on their local machines.

We recommend giving the Zulip development environment its own virtual
machine with at least 2GB of memory. If the Zulip development
environment will be the only thing running on the remote virtual
machine, we recommend installing
[directly][install-direct]. Otherwise, we recommend the
[Vagrant][install-vagrant] method so you can easily uninstall if you
need to.

## Connecting to the remote environment

The best way to connect to your server is using the command line tool `ssh`.

- On macOS and Linux/UNIX, `ssh` is a part of Terminal.
- On Windows, `ssh` comes with [Bash for Git][git-bash].

Open _Terminal_ or _Bash for Git_, and connect with the following:

```console
$ ssh username@host
```

If you have poor internet connectivity, we recommend using
[Mosh](https://mosh.org/) as it is more reliable over slow or unreliable
networks.

## Setting up user accounts

You will need a non-root user account with sudo privileges to set up
the Zulip development environment. If you have one already, continue
to the next section.

You can create a new user with sudo privileges by running the
following commands as root:

- You can create a `zulipdev` user by running the command
  `adduser zulipdev`. Run through the prompts to assign a password and
  user information. (You can pick any username you like for this user
  account.)
- You can add the user to the sudo group by running the command
  `usermod -aG sudo zulipdev`.
- Finally, you can switch to the user by running the command
  `su - zulipdev` (or just log in to that user using `ssh`).

## Setting up the development environment

After you have connected to your remote server, you need to install the
development environment.

If the Zulip development environment will be the only thing running on
the remote virtual machine, we recommend installing
[directly][install-direct]. Otherwise, we recommend the
[Vagrant][install-vagrant] method so you can easily uninstall if you
need to.

The main difference from the standard instructions is that for a
remote development environment, and you're not using our Digital Ocean
Droplet infrastructure (which handles `EXTERNAL_HOST` for you), you'll
need to run `export EXTERNAL_HOST=<REMOTE_IP>:9991` in a shell before
running `run-dev` (and see also the `--interface=''` option
documented below).

If your server has a static IP address, we recommend putting this
command in `~/.bashrc`, so you don't need to remember to run it every
time. This allows you to access Zulip running in your development
environment using a browser on another host.

## Running the development server

Once you have set up the development environment, you can start up the
development server with the following command in the directory where
you cloned Zulip:

```bash
./tools/run-dev --interface=''
```

This will start up the Zulip server on port 9991. You can then
navigate to `http://<REMOTE_IP>:9991` and you should see something like
this screenshot of the Zulip development environment:

![Image of Zulip development environment](../images/zulip-dev.png)

The `--interface=''` option makes the Zulip development environment
accessible from any IP address (in contrast with the much more secure
default of only being accessible from localhost, which is great for
developing on your laptop).

To properly secure your remote development environment, you can
[port forward](https://help.ubuntu.com/community/SSH/OpenSSH/PortForwarding)
using ssh instead of running the development environment on an exposed
interface. For example, if you're running Zulip on a remote server
such as a DigitalOcean Droplet or an AWS EC2 instance, you can set up
port-forwarding to access Zulip by running the following command in
your terminal:

```bash
ssh -L 3000:127.0.0.1:9991 <username>@<remote_server_ip> -N
```

Now you can access Zulip by navigating to `http://127.0.0.1:3000` in
your local computer's browser.

For more information, see [Using the development
environment][rtd-using-dev-env].

## Making changes to code on your remote development server

To see changes on your remote development server, you need to do one of the following:

- [Edit locally](#editing-locally): Clone Zulip code to your computer and
  then use your favorite editor to make changes. When you want to see changes
  on your remote Zulip development instance, sync with Git.
- [Edit remotely](#editing-remotely): Edit code directly on your remote
  Zulip development instance using a [Web-based IDE](#web-based-ide) (recommended for
  beginners) or a [command line editor](#command-line-editors), or a
  [desktop IDE](#desktop-gui-editors) using a plugin to sync your
  changes to the server when you save.

#### Editing locally

If you want to edit code locally install your favorite text editor. If you
don't have a favorite, here are some suggestions:

- [atom](https://atom.io/)
- [emacs](https://www.gnu.org/software/emacs/)
- [vim](https://www.vim.org/)
- [spacemacs](https://github.com/syl20bnr/spacemacs)
- [sublime](https://www.sublimetext.com/)
- [PyCharm](https://www.jetbrains.com/pycharm/)

Next, follow our [Git and GitHub guide](../git/index.md) to clone and configure
your fork of zulip on your local computer.

Once you have cloned your code locally, you can get to work.

##### Syncing changes

The easiest way to see your changes on your remote development server
is to **push them to GitHub** and then **fetch and merge** them from
the remote server.

For more detailed instructions about how to do this, see our [Git & GitHub
guide][rtd-git-guide]. In brief, the steps are as follows.

On your **local computer**:

1. Open _Terminal_ (macOS/Linux) or _Git for BASH_.
2. Change directory to where you cloned Zulip (e.g. `cd zulip`).
3. Use `git add` and `git commit` to stage and commit your changes (if you
   haven't already).
4. Push your commits to GitHub with `git push origin branchname`.

Be sure to replace `branchname` with the name of your actual feature branch.

Once `git push` has completed successfully, you are ready to fetch the commits
from your remote development instance:

1. In _Terminal_ or _Git BASH_, connect to your remote development
   instance with `ssh user@host`.
2. Change to the zulip directory (e.g., `cd zulip`).
3. Fetch new commits from GitHub with `git fetch origin`.
4. Change to the branch you want to work on with `git checkout branchname`.
5. Merge the new commits into your branch with `git merge origin/branchname`.

#### Editing remotely

There are a few good ways to edit code in your remote development
environment:

- With a command-line editor like vim or emacs run over SSH.
- With a desktop GUI editor like VS Code or Atom and a plugin for
  syncing your changes to the remote server.
- With a web-based IDE like CodeAnywhere.

We document these options below; we recommend using whatever editor
you prefer for development in general.

##### Desktop GUI editors

If you use [TextMate](https://macromates.com), Atom, VS Code, or a
similar GUI editor, tools like
[Visual Studio Code Remote - SSH](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-ssh) and
[rmate](https://github.com/textmate/rmate) that are designed to
integrate that editor with remote development over SSH allow you to
develop remotely from the comfort of your local machine.

Similar packages/extensions exist for other popular code editors as
well; contributions of precise documentation for them are welcome!

- [VSCode Remote - SSH][vscode-remote-ssh]: Lets you use Visual Studio
  Code against a remote repository with a similar user experience to
  developing locally.

[vscode-remote-ssh]: https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-ssh

- [rmate](https://github.com/textmate/rmate) for TextMate + VS Code:

1. Install the extension
   [Remote VSCode](https://marketplace.visualstudio.com/items?itemName=rafaelmaiolla.remote-vscode).
2. On your remote machine, run:
   ```console
   $ mkdir -p ~/bin
   $ curl -fL -o ~/bin/rmate https://raw.githubusercontent.com/textmate/rmate/master/bin/rmate
   $ chmod a+x ~/bin/rmate
   ```
3. Make sure the remote server is running in VS Code (you can
   force-start through the Command Palette).
4. SSH to your remote machine using
   ```console
   $ ssh -R 52698:localhost:52698 user@example.org
   ```
5. On your remote machine, run
   ```console
   $ rmate [options] file
   ```
   and the file should open up in VS Code. Any changes you make now will be saved remotely.

##### Command line editors

Another way to edit directly on the remote development server is with
a command line text editor on the remote machine.

Two editors often available by default on Linux systems are:

- **Nano**: A very simple, beginner-friendly editor. However, it lacks a lot of
  features useful for programming, such as syntax highlighting, so we only
  recommended it for quick edits to things like configuration files. Launch by
  running command `nano <filename>`. Exit by pressing _Ctrl-X_.

- **[Vim](https://www.vim.org/)**: A very powerful editor that can take a while
  to learn. Launch by running `vim <filename>`. Quit Vim by pressing _Esc_,
  typing `:q`, and then pressing _Enter_. Vim comes with a program to learn it
  called `vimtutor` (just run that command to start it).

Other options include:

- [emacs](https://www.gnu.org/software/emacs/)
- [spacemacs](https://github.com/syl20bnr/spacemacs)

##### Web-based IDE

If you are relatively new to working on the command line, or just want to get
started working quickly, we recommend web-based IDE
[Codeanywhere][codeanywhere].

To set up Codeanywhere for Zulip:

1. Create a [Codeanywhere][codeanywhere] account and log in.
2. Create a new **SFTP-SSH** project. Use _Public key_ for authentication.
3. Click **GET YOUR PUBLIC KEY** to get the new public key that
   Codeanywhere generates when you create a new project. Add this public key to
   `~/.ssh/authorized_keys` on your remote development instance.
4. Once you've added the new public key to your remote development instance, click
   _CONNECT_.

Now your workspace should look similar this:
![Codeanywhere workspace][img-ca-workspace]

#### Next steps

Next, read the following to learn more about developing for Zulip:

- [Git & GitHub guide][rtd-git-guide]
- [Using the development environment][rtd-using-dev-env]
- [Testing][rtd-testing]

[install-direct]: setup-advanced.md#installing-directly-on-ubuntu-debian-centos-or-fedora
[install-vagrant]: setup-recommended.md
[rtd-git-guide]: ../git/index.md
[rtd-using-dev-env]: using.md
[rtd-testing]: ../testing/testing.md
[git-bash]: https://git-for-windows.github.io/
[codeanywhere]: https://codeanywhere.com/
[img-ca-settings]: ../images/codeanywhere-settings.png
[img-ca-workspace]: ../images/codeanywhere-workspace.png

## Using an nginx reverse proxy

For some applications (e.g. developing an OAuth2 integration for
Facebook), you may need your Zulip development to have a valid SSL
certificate. While `run-dev` doesn't support that, you can do this
with an `nginx` reverse proxy sitting in front of `run-dev`.

The following instructions assume you have a Zulip Droplet working and
that the user is `zulipdev`; edit accordingly if the situation is
different.

1. First, get an SSL certificate; you can use
   [our certbot wrapper script used for production](../production/ssl-certificates.md#certbot-recommended)
   by running the following commands as root:

   ```bash
   # apt install -y crudini
   mkdir -p /var/lib/zulip/certbot-webroot/
   # if nginx running this will fail and you need to run `service nginx stop`
   /home/zulipdev/zulip/scripts/setup/setup-certbot \
     hostname.example.com \
     --email=username@example.com --method=standalone
   ```

1. Install nginx configuration:

   ```bash
   apt install -y nginx-full
   cp -a /home/zulipdev/zulip/tools/droplets/zulipdev /etc/nginx/sites-available/
   ln -nsf /etc/nginx/sites-available/zulipdev /etc/nginx/sites-enabled/
   nginx -t  # Verifies your nginx configuration
   service nginx reload  # Actually enabled your nginx configuration
   ```

1. Edit `zproject/dev_settings.py` to set
   `EXTERNAL_URI_SCHEME = "https://"`, so that URLs served by the
   development environment will be HTTPS.

1. Start the Zulip development environment with the following command:
   ```bash
   env EXTERNAL_HOST="hostname.example.com" ./tools/run-dev --interface=''
   ```
