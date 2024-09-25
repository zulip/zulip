# Server configuration

Once you've got Zulip set up, you'll likely want to configure it the
way you like.

## Making changes

Most configuration can be done by a realm administrator, on the web.
For those settings, see [the documentation for realm
administrators][realm-admin-docs].

[realm-admin-docs]: https://zulip.com/help/moving-to-zulip

This page discusses additional configuration that a system
administrator can do. To change any of the following settings, edit
the `/etc/zulip/settings.py` file on your Zulip server, and then
restart the server with the following command:

```bash
su zulip -c '/home/zulip/deployments/current/scripts/restart-server'
```

Zulip has dozens of settings documented in the comments in
`/etc/zulip/settings.py`; you can review [the latest version of the
settings.py template][settings-py-template], and if you've upgraded
from an old version of Zulip, we recommend [carefully updating your
`/etc/zulip/settings.py`][update-settings-docs] to fold in the inline
comment documentation for new configuration settings after upgrading
to each new major release.

[update-settings-docs]: upgrade.md#updating-settingspy-inline-documentation
[settings-py-template]: https://github.com/zulip/zulip/blob/main/zproject/prod_settings_template.py

Since Zulip’s settings file is a Python script, there are a number of
other things that one can configure that are documented in
[System and deployment configuration](system-configuration.md).
Otherwise, ask in [the Zulip development community](https://zulip.com/development-community/)
if there’s something you’d like to do but can’t figure out how to.

## Specific settings

### Domain and email settings

`EXTERNAL_HOST`: the user-accessible domain name for your Zulip
installation (i.e., what users will type in their web browser). This
should of course match the DNS name you configured to point to your
server and for which you configured SSL certificates. If you passed
`--hostname` to the installer, this will be prefilled with that value.

`ZULIP_ADMINISTRATOR`: the email address of the person or team
maintaining this installation and who will get support and error
emails. If you passed `--email` to the installer, this will be
prefilled with that value.

### Authentication backends

`AUTHENTICATION_BACKENDS`: Zulip supports a wide range of popular
options for authenticating users to your server, including Google
auth, GitHub auth, LDAP, SAML, REMOTE_USER, and more.

If you want an additional or different authentication backend, you
will need to uncomment one or more and then do any additional
configuration required for that backend as documented in the
`settings.py` file. See the
[section on authentication](authentication-methods.md) for more
detail on the available authentication backends and how to configure
them.

### Mobile and desktop apps

The Zulip apps expect to be talking to servers with a properly
signed SSL certificate, in most cases and will not accept a
self-signed certificate. You should get a proper SSL certificate
before testing the apps.

Because of how Google and Apple have architected the security model of
their push notification protocols, the Zulip mobile apps for
[iOS](https://itunes.apple.com/us/app/zulip/id1203036395) and
[Android](https://play.google.com/store/apps/details?id=com.zulipmobile)
can only receive push notifications from a single Zulip server. We
have configured that server to be `push.zulipchat.com`, and offer a
[push notification forwarding service](mobile-push-notifications.md) that
forwards push notifications through our servers to mobile devices.
Read the linked documentation for instructions on how to register for
and configure this service.

### Terms of Service and Privacy policy

Zulip allows you to configure your server's Terms of Service and
Privacy Policy pages (`/terms` and `/privacy`, respectively).

You can configure this using the `POLICIES_DIRECTORY` setting. We
recommend using `/etc/zulip/policies`, so that your policies are
naturally backed up with the server's other configuration. Just place
Markdown files named `terms.md` and `privacy.md` in that directory,
and set `TERMS_OF_SERVICE_VERSION` to `1.0` to enable this feature.

You can place additional files in this directory to document
additional policies; if you do so, you may want to:

- Create a Markdown file `sidebar_index.md` listing the pages in your
  policies site; this generates the policies site navigation.
- Create a Markdown file `missing.md` with custom content for 404s in
  this directory.

Please make clear in these pages what organization is hosting your
Zulip server, so that nobody could be confused that your policies are
the policies for Zulip Cloud.

### Miscellaneous server settings

Some popular settings in `/etc/zulip/settings.py` include:

- The Twitter integration, which provides pretty inline previews of
  tweets.
- The [email gateway](email-gateway.md), which lets
  users send emails into Zulip.
- The [Video call integrations](video-calls.md).

## Zulip announcement list

Subscribe to the [Zulip announcements email
list](https://groups.google.com/g/zulip-announce) for server administrators, if
you have not done so already. This extremely low-traffic list is for important
announcements, including [new releases](../overview/release-lifecycle.md) and
security issues.

## Enjoy your Zulip installation!

If you discover things that you wish had been documented, please
contribute documentation suggestions either via a GitHub issue or pull
request; we love even small contributions, and we'd love to make the
Zulip documentation cover everything anyone might want to know about
running Zulip in production.

Next: [Backups, export and import](export-and-import.md) and
[upgrading](upgrade.md) Zulip in production.
