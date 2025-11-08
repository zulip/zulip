# Server configuration

This page explains the configuration options in `/etc/zulip/settings.py`, the
main configuration file used by system administrators to configure their Zulip
server.

[Organization administrators][user-roles] can also [configure][realm-admin-docs]
many options for a Zulip organization from the web or desktop app. See [system
and deployment configuration documentation](system-configuration.md) for advanced
configuration of the various services that make up a complete Zulip installation
(`/etc/zulip/zulip.conf`).

[realm-admin-docs]: https://zulip.com/help/moving-to-zulip
[user-roles]: https://zulip.com/help/user-roles

## Server settings overview

The Zulip server self-documents more than a hundred settings in the
organized comments in `/etc/zulip/settings.py`. You can read [the
latest version of the settings.py template][settings-py-template] in a
browser.

[settings-py-template]: https://github.com/zulip/zulip/blob/main/zproject/prod_settings_template.py

Important settings in `/etc/zulip/settings.py` include:

- The mandatory `EXTERNAL_HOST` and `ZULIP_ADMINISTRATOR` settings,
  which are prefilled by the [installer](install.md).
- [Authentication methods](authentication-methods.md), including data
  synchronization options like LDAP and SCIM.
- The [email gateway](email-gateway.md), which lets
  users send emails into Zulip.
- [Video and voice call integrations](video-calls.md).
- How the server should store [uploaded files](upload-backends.md).

## Changing server settings

To change any of the settings in `/etc/zulip/settings.py`, modify and save the
file on your Zulip server, and restart the server with the following command:

```bash
su zulip -c '/home/zulip/deployments/current/scripts/restart-server'
```

If you have questions about how to configure your server, best-effort community
support is available in the [Zulip development community][chat-zulip-org].
Contact [sales@zulip.com](mailto:sales@zulip.com) to learn about paid support
options.

[chat-zulip-org]: https://zulip.com/development-community/

## Customizing user onboarding

### Navigation tour video

New users are offered a [2-minute video
tour](https://static.zulipchat.com/static/navigation-tour-video/zulip-10.mp4),
which shows where to find everything to get started with Zulip.

You can modify `NAVIGATION_TOUR_VIDEO_URL` in `/etc/zulip/settings.py` in order
to host the official video on your network, or to provide your own introductory
video with information on how your organization uses Zulip. A value of `None`
disables the navigation tour video experience.

### Terms of Service and Privacy policy

:::{important}

If you are using this feature, please make sure the name of your organization
appears prominently in all documents, to avoid confusion with policies for Zulip
Cloud.

:::

Zulip lets you configure your server's Terms of Service and
Privacy Policy pages.

Policy documents are stored as Markdown files in the configured
`POLICIES_DIRECTORY`. We recommend using `/etc/zulip/policies` as the directory,
so that your policies are naturally backed up with the server's other
configurations.

To provide Terms of Service and a Privacy Policy for your users, place Markdown
files named `terms.md` and `privacy.md` in the configured directory, and set
`TERMS_OF_SERVICE_VERSION` to `1.0` to enable this feature.

You can put additional files in the same directory to document other
policies; if you do so, you may want to:

- Create a Markdown file `sidebar_index.md` listing the pages in your
  policies site; this generates the policies site navigation.
- Create a Markdown file `missing.md` with custom content for 404s in
  this directory.
