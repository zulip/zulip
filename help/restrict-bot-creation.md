# Configure who can add bots

{!admin-only.md!}

Zulip lets you create three types of [bots](/help/bots-overview):

- **Incoming webhook bots**, which are limited to only sending messages into Zulip.
- **Generic bots**, which act like a normal user account.
- **Outgoing webhook bots**, which are generic bots that also receive
  new messages via HTTPS POST requests.

You can configure who can create incoming webhook bots (which are more limited
in what they can do), and who can create any bot. Both permissions can be
assigned to any combination of [roles](/help/user-roles), [groups](/help/user-groups), and
individual [users](/help/introduction-to-users).

!!! warn ""

    These settings only affect new bots. Existing bots will not be
    deactivated.

## Configure who can create bots that can only send messages (incoming webhook bots)

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Other permissions**, configure **Who can create bots that send messages into Zulip**.

{!save-changes.md!}

{end_tabs}

## Configure who can create any type of bot

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Other permissions**, configure **Who can create any bot**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Bots overview](/help/bots-overview)
* [Integrations overview](/help/integrations-overview)
* [Add a bot or integration](/help/add-a-bot-or-integration)
* [Deactivate or reactivate a bot](/help/deactivate-or-reactivate-a-bot)
* [Incoming webhooks](/api/incoming-webhooks-overview)
* [Outgoing webhooks](/api/outgoing-webhooks)
* [Non-webhook integrations](/api/non-webhook-integrations)
