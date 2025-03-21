# Move from self-hosting to Zulip Cloud

With Zulip's high quality import and export tools, you can always
move from self-hosting your own Zulip server to using the Zulip
Cloud service (and back).

## Process overview

To move your Zulip organization from a self-hosted server to Zulip
Cloud, you will need to take the following steps, which are described
in more detail below:

{start_tabs}

1. [Plan the process and coordinate with Zulip support](#plan-the-process-and-coordinate-with-zulip-support).

1. [Upgrade your self-hosted server](#upgrade-your-self-hosted-server).

1. [Export organization data](#export-organization-data).

1. [Decide how users will log in](#decide-how-users-will-log-in).

{end_tabs}

## Plan the process and coordinate with Zulip support

To import your self-hosted organization into Zulip Cloud, your server will need
to have the same database format as Zulip Cloud. Zulip Cloud is updated every
couple of weeks, so it's important to coordinate the timing with Zulip's support
team.

{start_tabs}

1. Review the process described on this page, and decide when you will be ready
   to make the transition.

1. Email [support@zulip.com](mailto:support@zulip.com) with the following information:
      - URL of the organization you plan to migrate
      - Your estimated timeline for generating a data export
      - Any other timing considerations for the transition (e.g., time of day)
      - If you're planning to purchase the [Zulip Cloud Plus
        plan](https://zulip.com/plans), details on the Plus plan features (e.g.,
        authentication methods) you intend to use. These features will be
        configured for your organization as part of the import process.

Zulip's support team will coordinate with you to make the transition with
minimal disruption for your team.

{end_tabs}

## Upgrade your self-hosted server

You will need to upgrade your server to use the same database format
as Zulip Cloud, using the published `zulip-cloud-current` branch.

{start_tabs}

1. [Check](/help/view-zulip-version#view-zulip-server-and-web-app-version) your
   Zulip server version.

1. [Upgrade to the latest maintenance
   release](https://zulip.readthedocs.io/en/stable/production/upgrade.html#upgrading-to-a-release)
   if you are running an older version of the Zulip server.

1. [Upgrade](https://zulip.readthedocs.io/en/stable/production/upgrade.html#upgrading-from-a-git-repository)
   to the `zulip-cloud-current` branch.

{end_tabs}

For additional support with upgrading from an older version of Zulip, contact
[sales@zulip.com](mailto:sales@zulip.com) for paid support options.

## Export organization data

{start_tabs}

1. Make sure you [have a
   plan](#plan-the-process-and-coordinate-with-zulip-support) for when the
   import into Zulip Cloud will take place.

1. Announce the migration and schedule Zulip downtime for your team.

1. [Follow these instructions](https://zulip.readthedocs.io/en/stable/production/export-and-import.html#data-export)
   to export your Zulip data.

1. Send an email to [support@zulip.com](mailto:support@zulip.com) with:
     - Your data export.
     - The subdomain you would like to use for your organization. Your Zulip
       Cloud organization will be hosted at `<subdomain>.zulipchat.com`.

Zulip's support team will let you know when the data import process is complete.

{end_tabs}

## Decide how users will log in

When user accounts are imported, users initially do not have passwords
configured. There are a few options for how users can log in for the first time.

!!! tip ""

    For security reasons, passwords are never exported.

### Allow users to log in with non-password authentication

Users will immediately be able to log in with [authentication
methods](/help/configure-authentication-methods) that do not require a password,
if these [authentication methods](/help/configure-authentication-methods) are
enabled.

### Send password reset emails to all users

You can ask [support@zulip.com](mailto:support@zulip.com) to send password reset
emails to all users in your organization, which will allow them to set an
initial password.

!!! warn ""

    To avoid confusion, first make sure that the users in your
    organization are aware that their account has been moved,
    and are expecting to receive a password reset email.

### Manual password resets

Alternatively, users can reset their own passwords by following the instructions
on your Zulip organization's login page.

## Advantages of Zulip Cloud

{!advantages-of-zulip-cloud.md!}

## Related articles

* [Choosing between Zulip Cloud and self-hosting](/help/zulip-cloud-or-self-hosting)
* [Zulip Cloud billing](/help/zulip-cloud-billing)
* [Upgrade Zulip server](https://zulip.readthedocs.io/en/stable/production/upgrade.html)
* [Zulip data export tool](https://zulip.readthedocs.io/en/stable/production/export-and-import.html#data-export)
