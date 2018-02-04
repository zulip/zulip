```eval_rst
:orphan:
```

# How to request a remote Zulip development instance

Under specific circumstances, typically during sprints, hackathons, and
Google Code-in, Zulip can provide you with a virtual machine with the
development environment already set up.

The machines (droplets) are being generously provided by
[Digital Ocean](https://www.digitalocean.com/). Thank you Digital Ocean!

## Step 1: Join GitHub and create SSH Keys

To contribute to Zulip and to use a remote Zulip developer instance, you'll
need a GitHub account. If you don't already have one, sign up
[here][github-join].

You'll also need to [create SSH keys and add them to your GitHub
account][github-help-add-ssh-key].

## Step 2: Create a fork of zulip/zulip

Zulip uses a **forked-repo** and **[rebase][gitbook-rebase]-oriented
workflow**. This means that all contributors create a fork of the [Zulip
repository][github-zulip-zulip] they want to contribute to and then submit pull
requests to the upstream repository to have their contributions reviewed and
accepted.

When we create your Zulip dev instance, we'll connect it to your fork of Zulip,
so that needs to exist before you make your request.

While you're logged in to GitHub, navigate to [zulip/zulip][github-zulip-zulip]
and click the **Fork** button. (See [GitHub's help article][github-help-fork]
for further details).

## Step 3: Make request via chat.zulip.org

Now that you have a GitHub account, have added your SSH keys, and forked
zulip/zulip, you are ready to request your Zulip developer instance.

If you haven't already, create an account on https://chat.zulip.org/.

Next, join the [development
help](https://chat.zulip.org/#narrow/stream/development.20help) stream. Create a
new **stream message** with your GitHub username as the **topic** and request
your remote dev instance. **Please make sure you have completed steps 1 and 2
before doing so**. A core developer should reply letting you know they're
working on creating it as soon as they are available to help.

Once requested, it will only take a few minutes to create your instance. You
will be contacted when it is complete and available.

## Next steps

Once your remote dev instance is ready:

- Connect to your server by running
  `ssh zulipdev@<username>.zulipdev.org` on the command line
  (Terminal for macOS and Linux, Bash for Git on Windows).
- There is no password; your account is configured to use your SSH keys.
- Once you log in, you should see `(zulip-py3-venv) ~$`.
- To start the dev server, `cd zulip` and then run `./tools/run-dev.py`.
- While the dev server is running, you can see the Zulip server in your browser
  at http://username.zulipdev.org:9991.

Once you've confirmed you can connect to your remote server, take a look at:

* [developing remotely](../development/remote.html) for tips on using the remote dev
  instance, and
* our [Git & GitHub Guide](../git/index.html) to learn how to use Git with Zulip.

Next, read the following to learn more about developing for Zulip:

* [Using the Development Environment](../development/using.html)
* [Testing](../testing/testing.html)

[github-join]: https://github.com/join
[github-help-add-ssh-key]: https://help.github.com/articles/adding-a-new-ssh-key-to-your-github-account/
[github-zulip-zulip]: https://github.com/zulip/zulip/
[github-help-fork]: https://help.github.com/articles/fork-a-repo/
[gitbook-rebase]: https://git-scm.com/book/en/v2/Git-Branching-Rebasing
