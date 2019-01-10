# Create a remote Zulip dev server

This guide is for mentors who want to help create remote Zulip dev servers
for hackathon, GCI, or sprint participants.

The machines (droplets) have been generously provided by
[Digital Ocean](https://www.digitalocean.com/) to help Zulip contributors
get up and running as easily as possible. Thank you Digital Ocean!

The `create.py` create uses the Digital Ocean API to quickly create new virtual
machines (droplets) with the Zulip dev server already configured.

## Step 1: Join Zulip Digital Ocean team

We have created a team on Digital Ocean for Zulip mentors. Ask Rishi or Tim
to be added. You need access to the team so you can create your Digital Ocean
API token.

## Step 2: Create your Digital Ocean API token

Once you've been added to the Zulip team,
[login](https://cloud.digitalocean.com/droplets) to the Digital Ocean control
panel and [create your personal API token][do-create-api-token]. **Make sure
you create your API token under the Zulip team.** (It should look something
like [this][image-zulip-team]).

Copy the API token and store it somewhere safe. You'll need it in the next
step.

## Step 3: Configure create.py

In `tools/droplets/` there is a sample configuration file `conf.ini-template`.

Copy this file to `conf.ini`:

```
$ cd tools/droplets/
$ cp conf.ini-template conf.ini
```

Now edit the file and replace `APITOKEN` with the personal API token you
generated earlier.

```
[digitalocean]
api_token = APITOKEN
```

Now you're ready to use the script.

## Usage

`create.py` takes two arguments

* GitHub username
* Tags (Optional argument)

```
$ python3 create.py <username>
$ python3 create.py <username> --tags <tag>
$ python3 create.py <username> --tags <tag1> <tag2> <tag3>
```
Assigning tags to droplets like `GCI` can be later useful for
listing all the droplets created during GCI.
[Tags](https://www.digitalocean.com/community/tutorials/how-to-tag-digitalocean-droplets)
may contain letters, numbers, colons, dashes, and underscores.

You'll need to run this from the Zulip development environment (e.g. in
Vagrant).

The script will also stop if a droplet has already been created for the
user. If you want to recreate a droplet for a user you can pass the
`--recreate` flag.

```
$ python3 create.py <username> --recreate
```
This will destroy the old droplet and create a new droplet for
the user.

In order for the script to work, the GitHub user must have:

- forked the [zulip/zulip][zulip-zulip] repository, and
- created an ssh key pair and added it to their GitHub account.

(Share [this link][how-to-request] with students if they need to do these
steps.)

The script will stop if it can't find the user's fork or ssh keys.

Once the droplet is created, you will see something similar to this message:

```
Your remote Zulip dev server has been created!

- Connect to your server by running
  `ssh zulipdev@<username>.zulipdev.org` on the command line
  (Terminal for macOS and Linux, Bash for Git on Windows).
- There is no password; your account is configured to use your ssh keys.
- Once you log in, you should see `(zulip-py3-venv) ~$`.
- To start the dev server, `cd zulip` and then run `./tools/run-dev.py`.
- While the dev server is running, you can see the Zulip server in your browser
  at http://<username>.zulipdev.org:9991.

See [Developing
remotely](https://zulip.readthedocs.io/en/latest/development/remote.html) for tips on
using the remote dev instance and [Git & GitHub
Guide](https://zulip.readthedocs.io/en/latest/git/index.html) to learn how to
use Git with Zulip.
```

Copy and paste this message to the user via Zulip chat. Be sure to CC the user
so they are notified.

[do-create-api-token]: https://www.digitalocean.com/community/tutorials/how-to-use-the-digitalocean-api-v2#how-to-generate-a-personal-access-token
[image-zulip-team]: http://cdn.subfictional.com/dropshare/Screen-Shot-2016-11-28-10-53-24-X86JYrrOzu.png
[zulip-zulip]: https://github.com/zulip/zulip
[python-digitalocean]: https://github.com/koalalorenzo/python-digitalocean
[how-to-request]: https://zulip.readthedocs.io/en/latest/development/request-remote.html

## Updating the base image

Rough steps:

1. Get the `ssh` key for `base.zulipdev.org` from Christie or Rishi.
1. Power up the `base.zulipdev.org` droplet from the digitalocean UI. You
   probably have to be logged in in the Zulip organization view, rather than
   via your personal account.
1. `ssh zulipdev@base.zulipdev.org`
1. `git pull upstream master`
1. `tools/provision`
1. `git clean -f`, in case things were added/removed from `.gitignore`.
1. `tools/run-dev.py`, let it run to completion, and then Ctrl-C (to clear
   out anything in the Rabbit MQ queue, load messages, etc).
1. `tools/run-dev.py`, and check that `base.zulipdev.org:9991` is up and running.
1. `> ~/.bash_history && history -c && sudo shutdown -h now` to clear any command
   line history (To reduce chance of confusing new contributors in case you made a typo)
   and shutdown the droplet.
1. Go to the Images tab on DigitalOcean, and "Take a Snapshot".
1. Wait for several minutes.
1. Make sure to add the appropriate regions via More -> "Add to region" in
   the Snapshots section.
1. Do something like `curl -X GET -H "Content-Type: application/json"
   -u <API_KEY>: "https://api.digitalocean.com/v2/images?page=5" | grep --color=always base.zulipdev.org`
   (maybe with a different page number, and replace your API_KEY).
1. Replace `template_id` in `create.py` in this directory with the
   appropriate `id`, and region with the appropriate region.
1. Test that everything works.
1. Open a PR with the updated template_id in zulip/zulip!

## Remotely debugging a droplet

To SSH into a droplet, first make sure you have a SSH key associated with your
github account, then ask the student to run the following in their
VM:

```
$ python3 ~/zulip/tools/droplets/add_mentor.py <your username>
```

You should now be able to connect to it using:

```
$ ssh zulipdev@<their username>.zulipdev.org
```

They can remove your SSH keys by running:

```
$ python3 ~/zulip/tools/droplets/add_mentor.py <your username> --remove
```
