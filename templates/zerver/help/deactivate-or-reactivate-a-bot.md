# Deactivate or reactivate a bot

Zulip realm administrators have the ability to deactivate or reactivate any bots
in their realm.

## Deactivate a bot

To properly remove a bot’s access to a Zulip organization, it does not suffice
to deactivate it in the SSO system, since that action does not prevent
authentication with any API keys the bot has.

Instead, you should deactivate the bot using the Zulip administration interface.

{!go-to-the.md!} [Bots](/#administration/bot-list-admin)
{!admin.md!}

4. Click the **Deactivate** button to the right of the bot that you want to
deactivate.

5. After clicking the **Deactivate** button, the button will transform into a
**Reactivate** button, and the **Name** and **Email** of the bot will be
stricken through, confirming the success of the bot's deactivation.

## Reactivate a bot

Zulip realm administrators can choose to reactivate a deactivated bot by
following the following steps.

{!go-to-the.md!} [Bots](/#administration/bot-list-admin)
{!admin.md!}

4. In the **Bots** section, click the **Reactivate** button to the right of the
bot that you want to reactivate.

5. After clicking the **Reactivate** button, the button will transform into a
**Deactivate** button, and the **Name** and **Email** of the bot will be cleared
of strikethrough, confirming the success of the bot's reactivation.
