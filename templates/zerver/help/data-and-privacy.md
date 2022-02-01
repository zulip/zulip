# Data and privacy

The makers of Zulip take your data and privacy very seriously. This page
provides detailed documentation on the data Zulip collects. For more information,
see also the [Zulip Privacy Policy](/policies/privacy).

## Desktop application

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

You can disable error reporting in the Zulip desktop app. If you do so, and the
app is connected only to self-hosted Zulip servers, no data will be uploaded to
Zulip.

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
