# Configure who can add bots

{!admin-only.md!}

By default, anyone other than guests can [add a bot](/help/add-a-bot-or-integration)
or integration to the Zulip organization. Organization administrators can
change who is allowed to add bots.

## Configure who can create any type of bot

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Other permissions**, configure **Who can create any bot**.

{!save-changes.md!}

{end_tabs}

## Configure who can create bots that can only send messages

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Other permissions**, configure **Who can create bots that send messages into Zulip**.

{!save-changes.md!}

{end_tabs}

!!! warn ""

    These settings only affect new bots. Existing bots will not be
    deactivated.

## Related articles

* [Bots overview](/help/bots-overview)
* [Integrations overview](/help/integrations-overview)
* [Add a bot or integration](/help/add-a-bot-or-integration)
* [Deactivate or reactivate a bot](/help/deactivate-or-reactivate-a-bot)
