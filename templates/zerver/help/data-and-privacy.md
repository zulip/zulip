# Data and privacy

The makers of Zulip take your data and privacy very seriously. This
page provides detailed documentation on some aspects of how Zulip
collects data. For more information, see also the [Zulip Privacy
Policy](/policies/privacy).

## Zulip Cloud

Zulip Cloud's privacy and data security practices are detailed in the
[Zulip Privacy Policy](/policies/privacy) and our [security
page](https://zulip.com/security).

## Self-hosted Zulip servers

Conceptually, our goal is for self-hosted servers to not make any
connections to servers managed by Zulip unless its operators configure
them to do so. Because Zulip installs various dependencies over the
network, including `apt`, `pip`, `yarn`, and from GitHub, installing a
Zulip server will make various outgoing network requests, most of them
to third parties that distribute software.  (The [Docker
image](https://github.com/zulip/docker-zulip) is a good way to install
Zulip on airgapped networks, if you want that).

By default, a self-hosted Zulip server makes no connections to servers
managed by Kandra Labs.

If you set up the [mobile push notifications
service](https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html),
your self-hosted Zulip server will make requests to the Zulip Cloud in
order to have mobile push notifications delivered to their users, as
detailed on the documentation for that feature.  Installations may
want to consider disabling the optional feature to send usage metadata
to Kandra Labs.

## Mobile apps

The mobile apps...

## Desktop app

When connected to a self-hosted Zulip server, the Zulip desktop app will send
data to Zulip only when it encounters an error. The error reports are processed
by Zulip's [third-party subprocessor](/help/gdpr-compliance#third-parties)
([Functional Software, Inc. d/b/a
Sentry](https://blog.sentry.io/2018/03/14/gdpr-sentry-and-you)), and reviewed by
the Zulip engineering team for the purpose of identifying, debugging, and fixing
bugs in the Zulip software.

The error reports contain basic device data, such as the operating system
(including version), hardware architecture, IP address, app version, and
potentially the hostname of the self-hosted Zulip server involved in the error.
Error reports do not have any information about other installed
applications.

You can disable error reporting in the Zulip desktop app by following
the below instructions. If you do so, and the app is connected only to
self-hosted Zulip servers, no data will be uploaded to Zulip.

### Disable desktop app error reporting

{start_tabs}
1. Click on the **gear** (<i class="fa fa-cog"></i>) icon in the bottom left of the
   Zulip desktop app.

2. In the **General** settings tab, find the **Advanced** section.

3. Toggle the **Enable error reporting** setting.

4. Restart the Zulip desktop app.
{end_tabs}

## Related articles

* [Privacy Policy](/policies/privacy)
* [GDPR compliance](/help/gdpr-compliance)
