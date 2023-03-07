# Create a remote Zulip dev server

This guide is for mentors who want to help create remote Zulip dev servers
for hackathon, GCI, or sprint participants.

The machines (droplets) have been generously provided by
[DigitalOcean](https://www.digitalocean.com/) to help Zulip contributors
get up and running as easily as possible. Thank you DigitalOcean!

The `create.py` create uses the DigitalOcean API to quickly create new virtual
machines (droplets) with the Zulip dev server already configured.

## Step 1: Join Zulip DigitalOcean team

We have created a team on DigitalOcean for Zulip mentors. Ask Rishi or Tim
to be added. You need access to the team so you can create your DigitalOcean
API token.

## Step 2: Create your DigitalOcean API token

Once you've been added to the Zulip team,
[log in](https://cloud.digitalocean.com/droplets) to the DigitalOcean control
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

- GitHub username
- Tags (Optional argument)

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
- created an SSH key pair and added it to their GitHub account.

(Share [this link][how-to-request] with students if they need to do these
steps.)

The script will stop if it can't find the user's fork or SSH keys.

Once the droplet is created, you will see something similar to this message:

```
Your remote Zulip dev server has been created!

- Connect to your server by running
  `ssh zulipdev@<username>.zulipdev.org` on the command line
  (Terminal for macOS and Linux, Bash for Git on Windows).
- There is no password; your account is configured to use your SSH keys.
- Once you log in, you should see `(zulip-py3-venv) ~$`.
- To start the dev server, `cd zulip` and then run `./tools/run-dev`.
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

1. Switch to the Zulip organization.
1. Create a new droplet, with:
   - "Regular with SSD" / "2GB RAM / 1 CPU"
   - Select your SSH key; this will not be built into the image, and
     is only for access to debug if the build does not succeed.
   - Check "Monitoring", "IPv6", and "User data"
   - Paste the contents of `tools/droplets/new-droplet-image` into the
     text box which says `Enter user data here...`
   - Name it e.g. `base-ubuntu-20-04.zulipdev.org`
1. Add an A record for `base.zulipdev.org` to point to the new host.
1. Wait for the host to boot.
1. `scp tools/droplets/new-droplet-image base.zulipdev.org:/tmp/new-droplet-image`
1. `ssh root@base.zulipdev.org bash /tmp/new-droplet-image`; this
   should take about 15 minutes to complete, and will finish by
   closing the connection and shutting the host down.
1. Go to the Snapshots tab on the image, and "Take a Snapshot".
1. Wait for several minutes for it to complete.
1. "Add to region" the snapshot into `NYC3`, `SFO3`, `BLR1`, and `FRA1`.
1. `curl -u <API_KEY>: https://api.digitalocean.com/v2/snapshots | jq .`
1. Replace `template_id` in `create.py` in this directory with the
   appropriate `id`.
1. Clean up by destroying the droplet (but _leaving_ all "associated
   resources"), and removing the DNS entry for `base.zulipdev.org`
1. Open a PR with the updated `template_id`.

## Remotely debugging a droplet

To SSH into a droplet, first make sure you have a SSH key associated with your
GitHub account, then ask the student to run the following in their
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

# Creating a production droplet

`create.py` can also create a production droplet quickly for testing purposes.

```
$ python3 create.py <username> --production
```
