# Export your organization

{!admin-only.md!}

!!! warn ""
    These instructions are specific to the hosted zulipchat.com service.
    If you're running your own server, you may be looking for our
    documentation on [server export and import][export-and-import] or
    [server backups][production-backups].

Zulip has high quality export tools that can be used to migrate from the
hosted Zulip Cloud service (zulipchat.com) to your own servers. There are
three types of zulipchat.com exports.

* **Public export**: An export of all users, settings, and all the data that
  appears in public streams.
* **Full export with member consent**: Everything in public export, plus all
  the private data of members that opt-in to the export.
* **Full export without member consent**: All the data in the organization.

All organizations have access to the first two kinds of export. Only corporate
Zulip Standard customers have access to **full export without member consent**.

## Request an export

The general pattern for all three types of export is

1. Email support@zulipchat.com with your zulipchat.com subdomain, the type
   of export you need, and additional information as needed for full exports
   (see below). Email us from the same address that you use to sign in
   to Zulip.

2. We will check that you are an organization administrator, and email you
   and all other organization administrators asking for a confirmation.

3. Reply confirming.

4. We will email a download link with the export to all administrators in
   the organization.

We can work with you to schedule a time for the export, to minimize downtime
during a transition from Zulip Cloud to an on-premises installation.

## Additional info needed for full exports

For **full export with member consent**, you will need to prove to us
which members' data you have consent to export (there are a few secure
and convenient options for doing this; contact support for details).

Such an export will include all the messages received by any user in
the organization that consented to the data export.  In particular, it
will include all public stream content and any private stream or
private message content where at least one of the participants gave
consent.

For **full export without member consent**, we will additionally need
evidence that you have authority to read members' private
messages. Typically, this will be because the zulipchat.com subdomain
is administered by a corporation, and you are an official
representative of that corporation. By requesting and approving this
export, you also assume full legal responsibility that the appropriate
employment agreements and corporate policy for this type of export are
in place. Note that many countries have laws that require employers to
notify employees of their use of such an export.

**Full export without member consent** is additionally limited to paid
Zulip Standard customers, though in rare cases may be available to
other organizations in case of due legal process.

## Related articles

* [Import into an on-premises installation][export-and-import]

[production-backups]: https://zulip.readthedocs.io/en/stable/production/maintain-secure-upgrade.html#backups
[export-and-import]: https://zulip.readthedocs.io/en/latest/production/export-and-import.html
