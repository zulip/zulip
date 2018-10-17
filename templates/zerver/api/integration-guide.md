# Writing a new integration

Integrations are one of the most important parts of a group chat tool
like Zulip, and we are committed to making integrating with Zulip and
getting your integration merged upstream so that everyone else can benefit
from it, as easy as possible while maintaining the high quality of the
Zulip integrations library.

On this page you'll find:

* An overview of the different [types of integrations](#types-of-integrations)
  possible with Zulip.
* [General advice](#general-advice) for writing integrations.
* Details about writing [incoming webhook integrations](/api/incoming-webhooks-overview).
* Details about writing [Python script and plugin
  integrations](#python-script-and-plugin-integrations).
* A guide to
  [documenting your integration][integration-docs-guide] is on a
  separate page.

[integration-docs-guide]: https://zulip.readthedocs.io/en/latest/subsystems/integration-docs.html

A detailed walkthrough of a simple "Hello World" integration can be
found in the [incoming webhook walkthrough](webhook-walkthrough).

Contributions to this guide are very welcome, so if you run into any
issues following these instructions or come up with any tips or tools
that help writing integration, please email
zulip-devel@googlegroups.com, open an issue, or submit a pull request
to share your ideas!

## Types of integrations

We have several different ways that we integrate with 3rd party
products, ordered here by which types we prefer to write:

1. **[Incoming webhook integrations](/api/incoming-webhooks-overview)** (examples:
   Freshdesk, GitHub), where the third-party service supports posting
   content to a particular URI on our site with data about the event.
   For these, you usually just need to create a new python package in
   the `zerver/webhooks/` directory.  You can easily find recent
   commits adding new integrations to crib from via
   `git log zerver/webhooks/`.

2. **[Python script integrations](#python-script-and-plugin-integrations)**
   (examples: SVN, Git), where we can get the service to call our integration
   (by shelling out or otherwise), passing in the required data.  Our preferred
   model for these is to ship these integrations in the
   [Zulip Python API distribution](https://github.com/zulip/python-zulip-api/tree/master/zulip),
   within the `integrations` directory there.

3. **[Plugin integrations](#python-script-and-plugin-integrations)** (examples:
   Jenkins, Hubot, Trac) where the user needs to install a plugin into their
   existing software.  These are often more work, but for some products are the
   only way to integrate with the product at all.

## Python script and plugin integrations

For plugin integrations, usually you will need to consult the
documentation for the third party software in order to learn how to
write the integration.  But we have a few notes on how to do these:

* You should always send messages by POSTing to URLs of the form
`https://zulip.example.com/v1/messages/`.

* We usually build Python script integration with (at least) 2 files:
`zulip_foo_config.py` containing the configuration for the
integration including the bots' API keys, plus a script that reads
from this configuration to actually do the work (that way, it's
possible to update the script without breaking users' configurations).

* Be sure to test your integration carefully and document how to
  install it (see notes on documentation below).

* You should specify a clear HTTP User-Agent for your integration. The
user agent should at a minimum identify the integration and version
number, separated by a slash. If possible, you should collect platform
information and include that in `()`s after the version number. Some
examples of ideal UAs are:

```
ZulipDesktop/0.7.0 (Ubuntu; 14.04)
ZulipJenkins/0.1.0 (Windows; 7.2)
ZulipMobile/0.5.4 (Android; 4.2; maguro)
```
