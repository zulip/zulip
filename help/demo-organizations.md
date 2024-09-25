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
   edit the **Name** field.

1. Click **Add**.

1. You will receive a confirmation email within a few minutes. Open
   it and click **Confirm and set password**.

{end_tabs}

## Convert a demo organization to a permanent organization

{!owner-only.md!}

If you'd like to keep your demo organization user and message history,
you can convert it to a permanent Zulip organization. You'll need to
choose a new subdomain for your new permanent organization URL.

Also, as part of the process of converting a demo organization to a
permanent organization:

* Users will be logged out of existing sessions on the web, mobile and
  desktop apps and need to log in again.
* Any [API clients](/api/) or [integrations](/integrations/) will need
  to be updated to point to the new organization URL.

{start_tabs}

{settings_tab|organization-profile}

1. Click the **Convert to make it permanent** link at the end of the
   "This demo organization will be automatically deleted ..." notice.

1. Enter the subdomain you would like to use for the new organization
   URL and click  **Convert**.

!!! warn ""

    **Note:** You will be logged out when the demo organization is
    successfully converted to a permanent Zulip organization and be
    redirected to new organization URL log-in page.

{end_tabs}

## Related articles

* [Getting started with Zulip](/help/getting-started-with-zulip)
* [Moving to Zulip](/help/moving-to-zulip)
* [Invite users to join](/help/invite-users-to-join)
