# Export your organization

!!! warn ""

    If you're self-hosting Zulip, you may want to check out the
    documentation on [server export and import][export-and-import] or
    [server backups][production-backups].

Zulip has high quality export tools that can be used to migrate between the
hosted Zulip Cloud service and your own servers. Two types of data exports are
available for all Zulip organizations:

* [**Export of public
   data**](#export-for-migrating-to-zulip-cloud-or-a-self-hosted-server):
   Complete data for your organization *other than* [private
   channel](/help/channel-permissions#private-channels) messages and [direct
   messages](/help/direct-messages). This export includes user settings and
   channel subscriptions.

* [**Standard
  export**](#export-for-migrating-to-zulip-cloud-or-a-self-hosted-server):
  Everything in the export of public data, plus all the [private
  channel](/help/channel-permissions#private-channels) messages and [direct
  messages](/help/direct-messages) that members who have
  [allowed](#configure-whether-administrators-can-export-your-private-data)
  administrators to export their private data can access.

Two additional types of data exports are available to **corporate** [Zulip Cloud
Standard][plans] and [Zulip Cloud Plus][plans] customers:

[plans]: https://zulip.com/plans/

* [**Full export without member consent**](#full-export-without-member-consent):
  All the data in the organization.

* [**Compliance export**](#compliance-export): A targeted, human-readable export
  of messages matching some combination of criteria (e.g., sender, recipient,
  message keyword, or timestamp).

## Export for migrating to Zulip Cloud or a self-hosted server

{!admin-only.md!}

{!not-human-export-format.md!}

{start_tabs}

{settings_tab|data-exports-admin}

1. Click **Start export**.

1. Select the desired **Export type**.

1. Click **Start export** to begin the export process. After a few minutes,
   you'll be able to download the exported data from the list of
   data exports.

1. Use [Zulip's logical data import tool][import-only] to import your data into
   a self-hosted server. For Zulip Cloud imports, contact
   [support@zulip.com](mailto:support@zulip.com).

!!! warn ""

    Generating the export can take up to an hour for organizations
    with a large number of messages or uploaded files.

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

      1. What limits you would like on the export.  Currently, compliance
         exports can apply any combination of the following filters:

         - Message sender
         - Message recipient
         - Message contents, by specific keywords
         - Sent timestamp before, after, or between dates

         If you need other limits, please ask.

      1. Your preferred format for the export: CSV or JSON.

      1. Whether or not you want to receive copies of all attachments referenced in
         the exported messages.

1. You will receive the requested information once your authority to request the
   export has been verified.

{end_tabs}

## Configure whether administrators can export your private data

{start_tabs}

{settings_tab|account-and-privacy}

1. Under **Privacy**, toggle **Let administrators export my private data**.

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
