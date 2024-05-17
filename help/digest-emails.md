# Weekly digest emails

{!admin-only.md!}

Zulip has a beta feature to send weekly emails to users who haven't
been active for 5 or more days.  These emails include details on new
channels created and highlights of traffic (of subscribed channels) that
can intrigue users.

This feature is disabled by default, but an organization administrator
can enable it for their organization.  Individual users can opt-out in
organizations that have enabled it.

You can view a sample digest email for your account in HTML and
plain-text formats by visiting `https://zulip.example.com/digest/`,
if `https://zulip.example.com` is your Zulip server URL.

## Enable digest emails for an organization

{start_tabs}

{settings_tab|organization-settings}

1. Under **Automated messages and emails**, toggle
   **Send weekly digest emails to inactive users**.

{end_tabs}
