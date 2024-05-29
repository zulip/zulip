Get Zulip notifications when you `hg push`!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1.  {!download-python-bindings.md!}

1.  Edit the `hg/.hgrc` configuration file for this default Mercurial
repository and add the following sections, using the credentials for
your Mercurial bot and setting the appropriate path to the integration
hook if it installs in a different location on this system:

        [hooks]
        changegroup = python:zulip_changegroup.hook

        [zulip]
        email = "hg-bot@example.com"
        api_key = "0123456789abcdefg"
        stream = "commits"
        site = {{ api_url }}

1.  Add the directory where the `zulip_changegroup.py` script was
installed to the environment variable `PYTHONPATH`.  For example, if
you installed the Zulip Python bindings at the system level, it'd be:

        export PYTHONPATH=/usr/local/share/zulip/integrations/hg:$PYTHONPATH

That’s all it takes for the basic setup! On the next `hg push`, you’ll
get a Zulip update for the changeset.

### More configuration options

The Mercurial integration also supports:

-   linking to changelog and revision URLs for your repository’s web UI
-   branch whitelists and blacklists

#### Web repository links

If you’ve set up your repository to be [browsable via the web][1],
add a `web_url` configuration option to the `zulip` section of your
default `.hg/hgrc` to get changelog and revision links in your Zulip
notifications:

    [zulip]
    email = "hg-bot@example.com"
    api_key = "0123456789abcdefg"
    stream = "commits"
    web_url = "http://hg.example.com:8000/"
    site = {{ api_url }}

[1]: https://www.mercurial-scm.org/wiki/QuickStart#Network_support

#### Branch whitelists and blacklists

By default, this integration will send Zulip notifications for
changegroup events for all branches. If you’d prefer to only receive
Zulip notifications for specified branches, add a `branches`
configuration option to the `zulip` section of your default `.hg/hgrc`,
containing a comma-separated list of the branches that should produce
notifications:

    [zulip]
    email = "hg-bot@example.com"
    api_key = "0123456789abcdefg"
    stream = "commits"
    branches = "prod,default"

You can also exclude branches that you don’t want to cause
notifications. To do so, add an `ignore_branches` configuration option
to the `zulip` section of your default `.hg/hgrc`, containing a
comma-separated list of the branches that should be ignored:

    [zulip]
    email = "hg-bot@example.com"
    api_key = "0123456789abcdefg"
    stream = "commits"
    ignore_branches = "noisy,even-more-noisy"

When team members push new changesets with `hg push`, you’ll get a
Zulip notification.

{!congrats.md!}

![Mercurial bot message](/static/images/integrations/hg/001.png)
