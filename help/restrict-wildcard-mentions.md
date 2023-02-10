# Restrict wildcard mentions

{!admin-only.md!}

Organization administrators can set a policy for which users are
allowed to use [wildcard
mentions](/help/dm-mention-alert-notifications#wildcard-mentions) in
large streams (defined for this purpose as streams with more than 15
subscribers).

Zulip allows anyone to use wildcard mentions in streams with at most
15 subscribers. The default allows only organization administrators to
use wildcard mentions in large streams.

Users permitted to use wildcard mentions by the organization's policy
are warned that wildcard mentions will result in all subscribers
receiving email and mobile push notifications.

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Stream permissions**, configure
   **Who can use @all/@everyone mentions in large streams**.

{!save-changes.md!}

{end_tabs}
