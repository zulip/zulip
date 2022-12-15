#### Import into a self-hosted Zulip server

Zulip's import tools are robust, and have been used to import workspaces
with 10,000 members and millions of messages. If you're planning on doing
an import much larger than that, or run into performance issues when
importing, [contact us](/help/contact-support) for help.

1. Follow steps
   [1](https://zulip.readthedocs.io/en/stable/production/install.html#step-1-download-the-latest-release)
   and
   [2](https://zulip.readthedocs.io/en/stable/production/install.html#step-2-install-zulip)
   of the guide for [installing a new Zulip
   server](https://zulip.readthedocs.io/en/stable/production/install.html).

1. Copy the **exported data** file containing your workspace message
   history export onto your Zulip server, and put it in `/tmp/`.

1. Log in to a shell on your Zulip server as the `zulip` user.
