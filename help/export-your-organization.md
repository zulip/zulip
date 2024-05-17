# Export your organization

!!! warn ""

    These instructions are specific to the hosted Zulip Cloud service.
    If you're running your own server, you may be looking for our
    documentation on [server export and import][export-and-import] or
    [server backups][production-backups].

Zulip has high quality export tools that can be used to migrate from the hosted
Zulip Cloud service to your own servers. Two types of data exports are available
to all Zulip Cloud organizations:

* [**Export of public data**](#export-of-public-data): Complete data for your
   organization *other than* [private channel](/help/channel-permissions) messages
   and [direct messages](/help/direct-messages).

* [**Full export with member consent**](#full-export-with-member-consent):
  Everything in the export of public data, plus all the [private
  channel](/help/channel-permissions) messages and [direct
  messages](/help/direct-messages) of members who opt in to have their data
  exported.

Two additional types of data exports are available to **corporate** [Zulip Cloud
Standard][plans] and [Zulip Cloud Plus][plans] customers:

[plans]: https://zulip.com/plans/

* [**Full export without member consent**](#full-export-without-member-consent):
  All the data in the organization.

* [**Compliance export**](#compliance-export): A targeted, human-readable export
  of messages matching some combination of criteria (e.g., sender, recipient,
  message keyword, or timestamp).

## Export of public data

{!admin-only.md!}

{!not-human-export-format.md!}

{start_tabs}

{settings_tab|data-exports-admin}

1. Click **Start export of public data**.

1. After a few minutes, you'll be able to download the export as a `.tar.gz`
file from that page.

1. Import the tarball using [Zulip's logical data import tool][import-only].

!!! warn ""

    Generating the export can take up to an hour for organizations
    with a large number of messages or uploaded files.

{end_tabs}

## Full export with member consent

{!owner-only.md!}

{!not-human-export-format.md!}

In addition to your organization's public data, this export includes all the
messages received by any user in the organization who consents to the data
export. In particular, it includes any [private
channel](/help/channel-permissions) messages and [direct
messages](/help/direct-messages) where *at least one of the recipients* has
given consent.

Users who do not provide consent will have their settings and channel
subscriptions exported, but will have no personalized message history.

{start_tabs}

1. Email [support@zulip.com](mailto:support@zulip.com) with your
   organization's `zulipchat.com` URL, asking for a **full export with
   member consent**. Please send the email from the same address
   that you use to sign in to Zulip, so that Zulip Support can verify
   that you are an owner of the organization.

1. You will receive an email with instructions on how to collect member consent.
   Follow the instructions, and notify
   [support@zulip.com](mailto:support@zulip.com) when the process has been
   completed.

1. You will receive an archive in the `.tar.gz` format containing all public
   information for your organization, plus [private
   channel](/help/channel-permissions) messages and [direct
   messages](/help/direct-messages) for users who gave consent.

1. Import the tarball using [Zulip's logical data import tool][import-only].

{end_tabs}

## Full export without member consent

{!owner-only.md!}

{!not-human-export-format.md!}

{!export-without-consent-requirements.md!}

{start_tabs}

1. Email [support@zulip.com](mailto:support@zulip.com) with your
   organization's `zulipchat.com` URL, asking for a **full export without
   member consent**. Please send the email from the same address
   that you use to sign in to Zulip, so that Zulip Support can verify
   that you are an owner of the organization.

1. Once your authority to request the export has been verified, you will receive
   an archive in the `.tar.gz` format containing all the information for your
   organization.

1. Import the tarball using [Zulip's logical data import tool][import-only].

{end_tabs}

## Compliance export

{!owner-only.md!}

This type of export is recommended if you plan to work with the exported data
directly (e.g., reading messages or processing them with a script), rather than
importing the export into a new Zulip organization.

{!export-without-consent-requirements.md!}

{start_tabs}

1. Email [support@zulip.com](mailto:support@zulip.com) asking for a **compliance
   export**. Please send the email from the same address that you use to sign in
   to Zulip, so that Zulip Support can verify that you are an owner of the
   organization. You will need to specify:

      1. The `zulipchat.com` URL for your organization

      2. What limits you would like on the export.  Currently, compliance
         exports can apply any combination of the following filters:

         - Message sender
         - Message recipient
         - Message contents, by specific keywords
         - Sent timestamp before, after, or between dates

         If you need other limits, please ask.

      3. Your preferred format for the export: CSV or JSON.

      4. Whether or not you want to receive copies of all attachments referenced in
         the exported messages.

1. You will receive the requested information once your authority to request the
   export has been verified.

{end_tabs}

## Related articles

* [Change organization URL](/help/change-organization-url)
* [Deactivate your organization](/help/deactivate-your-organization)
* [Import organization into a self-hosted Zulip server][import-only]
* [Compliance exports for self-hosted organizations][compliance-exports-self-hosted]

[production-backups]: https://zulip.readthedocs.io/en/stable/production/export-and-import.html#backups
[export-and-import]: https://zulip.readthedocs.io/en/stable/production/export-and-import.html#data-export
[import-only]: https://zulip.readthedocs.io/en/stable/production/export-and-import.html#import-into-a-new-zulip-server
[compliance-exports-self-hosted]: https://zulip.readthedocs.io/en/stable/production/export-and-import.html#compliance-exports
