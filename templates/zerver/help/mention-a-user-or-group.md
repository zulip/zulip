# Mention a user or group

You can mention a team member or [user group](/help/user-groups) to call their attention to a
message. Mentions follow the same
[notification settings](/help/pm-mention-alert-notifications) as private
messages and alert words.

### From the compose box

{start_tabs}

{!start-composing.md!}

2. Type `@` followed by a few letters from a name or email address.

3. Pick the appropriate user or user group from the autocomplete.

{end_tabs}

### From the user list

{start_tabs}

1. Hover over a user in the right sidebar.

1. Click the ellipsis (<i class="zulip-icon ellipsis-v-solid"></i>) to the right.

1. Select **Reply mentioning user**.

{end_tabs}

Alternatively, click on the profile picture of any user in the main message feed.

## Silently mention a user

A silent mention allows you to refer to a user without triggering a
notification. Silent mentions start with `@_` instead of `@`.

{start_tabs}

{!start-composing.md!}

2. Type `@_` followed by a few letters from a name or email address.

3. Pick the appropriate user or user group from the autocomplete.

{end_tabs}

## Mention everyone on a stream

You can mention everyone on a stream with the `@**all**` mention. Use
sparingly! Used improperly, wildcard mentions can be annoying.

Note that this will not notify anyone who has muted the stream, and
users can disable receiving email/push notifications for these
wildcard mentions, either
[globally](/help/pm-mention-alert-notifications) or for [individual
streams](/help/stream-notifications).

### Restrictions on wildcard mentions

Organization administrators can set a policy for which users are
allowed to use wildcard mentions.

Zulip allows anyone to use wildcard mentions in streams with at most
15 subscribers.

Organizations administrators can configure a policy for which classes
of users are allowed to use wildcard mentions in streams with more
than 15 subscribers.  The default allows only organization
administrators to use wildcard mentions in large streams.

Users permitted to use wildcard mentions by the organization's policy
are warned that wildcard mentions result in everyone receiving email
and mobile push notifications.

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Organization permissions**, configure
   **Who can use wildcard mentions in large streams**.

{!save-changes.md!}

{end_tabs}
