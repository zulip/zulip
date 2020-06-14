# Export your organization

!!! warn ""
    These instructions are specific to the hosted Zulip Cloud service.
    If you're running your own server, you may be looking for our
    documentation on [server export and import][export-and-import] or
    [server backups][production-backups].

Zulip has high quality export tools that can be used to migrate from the
hosted Zulip Cloud service (zulip.com) to your own servers. There are
three types of Zulip Cloud exports.

* **Public export**: An export of all users, settings, and all the data that
  appears in public streams.
* **Full export with member consent**: Everything in public export, plus all
  the private data of members that opt-in to the export.
* **Full export without member consent**: All the data in the organization.

All organizations have access to the first two kinds of export. Only corporate
Zulip Standard customers have access to **full export without member consent**.

## Public export

{!admin-only.md!}

{start_tabs}

{settings_tab|data-exports-admin}

1. Click **Start public export**.

1. After a few minutes, you'll be able to download the export as a `.tar.gz`
file from that page.

1. Import the tarball using [Zulip's logical data import tool][import-only].

{end_tabs}

Note that generating the export can take up to an hour for organizations
with lots of messages or uploaded files.

## Full export with member consent

{!owner-only.md!}

{start_tabs}

1. Email support@zulip.com with your organization's zulip.com URL, asking for
   a full export with member consent. Email us from the same address that
   you use to sign in to Zulip.

1. We will verify that you are an organization administrator, and email you
   instructions on how to collect member consent.

1. The end result of that process with be an archive in the same
   format as the public exports discussed above, including extra
   private stream and private message data for users who gave consent.

1. Import the tarball using [Zulip's logical data import tool][import-only].

{end_tabs}

Note that such an export will include all the messages received by any user
in the organization that consents to the data export.  In particular, it
will include all public stream content and any private stream or private
message content where at least one of the participants gives consent.

Users who do not provide consent will have their settings and stream
subscriptions exported, but will otherwise be treated as new users after
import.

## Full export without member consent

{!owner-only.md!}

This export is limited to paid Zulip Standard customers, though in rare
cases may be available to other organizations in case of due legal process.

To start this export, email support@zulip.com with your zulip.com
URL, asking for a full export without member consent.

You'll also need to email us evidence that you have authority to read
members' private messages. Typically, this will be because the zulip.com
URL is administered by a corporation, and you are an official
representative of that corporation. By requesting and approving this export,
you will also assume full legal responsibility that the appropriate employment
agreements and corporate policy for this type of export are in place. Note
that many countries have laws that require employers to notify employees of
their use of such an export.

## Related articles

* [Import into an on-premises installation][import-only]

[production-backups]: https://zulip.readthedocs.io/en/stable/production/export-and-import.html#backups
[export-and-import]: https://zulip.readthedocs.io/en/latest/production/export-and-import.html#data-export
[import-only]: https://zulip.readthedocs.io/en/latest/production/export-and-import.html#import-into-a-new-zulip-server
