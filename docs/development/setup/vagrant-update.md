If after rebasing onto a new version of the Zulip server, you receive
new errors while starting the Zulip server or running tests, this is
probably not because Zulip's `main` branch is broken. Instead, this
is likely because we've recently merged changes to the development
environment provisioning process that you need to apply to your
development environment. To update your environment, you'll need to
re-provision your Vagrant machine using `vagrant provision` (this just
runs `tools/provision` from your Zulip checkout inside the Vagrant
guest); this should complete in about a minute.

After provisioning, you'll want to
[(re)start the Zulip development server](/development/setup-recommended.md#step-3-start-the-development-environment).

If you run into any trouble, [#provision
help](https://chat.zulip.org/#narrow/channel/21-provision-help) in the
[Zulip development community
server](https://zulip.com/development-community/) is a great place to ask for
help.
