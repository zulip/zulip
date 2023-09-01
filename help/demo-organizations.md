# Demo organizations

!!! warn ""

    **Note:** The ability to create demo organizations is an upcoming
    feature. It is not available yet.

If you would like to try out Zulip without having to make any
decisions (like how to name your organization or whether to import
data from an existing chat tool), you can create a Zulip demo
organization.

Demo organizations differ from a regular Zulip organization in a few
ways:

* A demo organization will be automatically deleted 30 days after
  creation. You can [convert a demo organization into a regular
  organization](#convert-a-demo-organization-to-a-permanent-organization)
  if you'd prefer to keep its history.
* You do not need to choose a URL or when creating a demo organization;
  one will be generated automatically for you.
* A demo organization cannot be directly upgraded to a paid Zulip
  Cloud plan without first converting to a regular organization.

Other than those limitations, they work exactly like a normal Zulip
organization; you can invite additional users, connect the mobile
apps, etc.

## Create a demo organization

{start_tabs}

1. Go to zulip.com and click **New organization** in the top-right corner.

{end_tabs}

## Configure email for demo organization owner

To convert a demo organization to a permanent organization, and to access
certain features like [inviting other users](/help/invite-new-users) and
[configuring authentication methods](/help/configure-authentication-methods),
the creator of the demo organization will need to add an email address
and set a password for their account.

{start_tabs}

{settings_tab|account-and-privacy}

1. Under **Account**, click **Add email**.

1. Enter your email address.

1. *(optional)* If the name on the account is still a placeholder,
   edit the **Full name** field.

1. Click **Add**.

1. You will receive a confirmation email within a few minutes. Open
   it and click **Confirm and set password**.

{end_tabs}

## Convert a demo organization to a permanent organization

{start_tabs}

{settings_tab|organization-profile}

1. Click the **Convert organization** link at the end of the red
   "This is a demo organization" notice on top.

1. Enter the URL you would like to use for the organization and click
   **Convert**.

{end_tabs}

## Related articles

* [Getting started with Zulip](/help/getting-started-with-zulip)
* [Setting up your organization](/help/getting-your-organization-started-with-zulip)
* [Invite users to join](/help/invite-users-to-join)
