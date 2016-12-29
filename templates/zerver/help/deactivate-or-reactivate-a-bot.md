# Deactivate or reactivate a bot

Zulip realm administrators have the ability to deactivate or reactivate any bots
in their realm.

## Deactivate a bot

To properly remove a bot’s access to a Zulip organization, it does not suffice
to deactivate it in the SSO system, since that action does not prevent
authentication with any API keys the bot has.

Instead, you should deactivate the bot using the Zulip administration interface.

1. Click the cog (![cog](/static/images/help/cog.png)) in the upper right corner
of the right sidebar.

2. Select **Administration** from the dropdown menu that appears.

    ![Administration dropdown](/static/images/help/administration.png)

3. Upon clicking **Administration**, your view will be replaced with the
**Administration** page. Click the **Bots** tab at the top of the
panel; it turns gray upon hover.

    ![Administration](/static/images/help/admin-panel-bots.png)

4. In the **Bots** section, click the red **Deactivate** button to the right of
the bot that you want to deactivate.

    ![Deactivate Bots](/static/images/help/deactivate-panel-bots.png)

5. After clicking the **Deactivate** button, the button will transform into
a orange **Reactivate** button, and the **Name** and **Email** of the bot will
be stricken through, confirming the success of the bot's deactivation.

    ![Deactivate Bot Success](/static/images/help/bot-deactivate-success.png)

## Reactivate a bot

Zulip realm administrators can choose to reactivate a deactivated bot by
following the following steps.

1. Click the cog (![cog](/static/images/help/cog.png)) in the upper right corner
of the right sidebar.

2. Select **Administration** from the dropdown menu that appears.

    ![Administration dropdown](/static/images/help/administration.png)

3. Upon clicking **Administration**, your view will be replaced with the
**Administration** page. Click the **Bots** tab at the top of the
panel; it turns gray upon hover.

    ![Administration](/static/images/help/admin-panel-bots.png)

4. In the **Bots** section, click the orange **Reactivate** button to the right of
the bot that you want to reactivate.

    ![Reactivate Bots](/static/images/help/reactivate-panel-bots.png)

5. After clicking the **Reactivate** button, the button will transform into
a red **Deactivate** button, and the **Name** and **Email** of the bot will
be cleared of strikethrough, confirming the success of the bot's reactivation.

    ![Reactivate Bot Success](/static/images/help/bot-reactivate-success.png)
