# Customize Zulip

Once you've got Zulip setup, you'll likely want to configure it the
way you like.  Most configuration can be done by a realm administrator
on the web (see
[the documentation for realm administrators](https://zulipchat.com/help/getting-your-organization-started-with-zulip);
this page discusses those additional configuration items that can be
done by a system administrator.

## Mobile and desktop apps

The Zulip apps expect to be talking to to servers with a properly
signed SSL certificate, in most cases and will not accept a
self-signed certificate.  You should get a proper SSL certificate
before testing the apps.

Because of how Google and Apple have architected the security model of
their push notification protocols, the Zulip mobile apps for
[iOS](https://itunes.apple.com/us/app/zulip/id1203036395) and
[Android](https://play.google.com/store/apps/details?id=com.zulip.android)
can only receive push notifications from a single Zulip server.  We
have configured that server to be `push.zulipchat.com`, and offer a
[push notification forwarding service](prod-mobile-push-notifications.html) that
forwards push notifications through our servers to mobile devices.
Read the linked documentation for instructions on how to register for
and configure this service.

By the end of summer 2017, all of the Zulip apps will have full
support for multiple accounts, potentially on different Zulip servers,
with a convenient UI for switching between them.

## Terms of service and Privacy policy

Zulip allows you to configure your server's Terms of Service and
Privacy Policy pages (`/terms` and `/privacy`, respectively).  You can
use the `TERMS_OF_SERVICE` and `PRIVACY_POLICY` settings to configure
the path to your server's policies.  The syntax is Markdown (with
support for included HTML).  A good approach is to use paths like
`/etc/zulip/terms.md`, so that it's easy to back up your policy
configuration along with your other Zulip server configuration.

## Miscellaneous server settings

Zulip has dozens of settings documented in the comments in
`/etc/zulip/settings.py`; you can review
[the latest version of the settings.py template][settings-py-template]
if you've deleted the comments or want to check if new settings have
been added in more recent versions of Zulip.

Since Zulip's settings file is a Python script, there are a number of
other things that one can configure that are not documented; ask on
[chat.zulip.org](https://zulip.readthedocs.io/en/latest/chat-zulip-org.html)
if there's something you'd like to do but can't figure out how to.

[settings-py-template]: https://github.com/zulip/zulip/blob/master/zproject/prod_settings_template.py

## Zulip announcement list

If you haven't already, subscribe to the
[zulip-announce](https://groups.google.com/forum/#!forum/zulip-announce)
list so that you can receive important announces like new Zulip
releases or major changes to the app ecosystem..

## Enjoy your Zulip installation!

If you discover things that you wish had been documented, please
contribute documentation suggestions either via a GitHub issue or pull
request; we love even small contributions, and we'd love to make the
Zulip documentation cover everything anyone might want to know about
running Zulip in production.

Next: [Maintaining and upgrading Zulip in
production](prod-maintain-secure-upgrade.html).
