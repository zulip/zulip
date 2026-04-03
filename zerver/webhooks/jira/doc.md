# Zulip Jira integration

Get Zulip notifications for your Jira projects!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. Decide where to send {{ integration_display_name }} notifications, and
   [generate the integration URL](/help/generate-integration-url). To
   generate a Jira API token, follow
   [Atlassian's documentation](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/).

    !!! tip ""

        If you also configure **Your Jira email** and **Your Jira API
        token**, this integration will show display names for users
        mentioned in Jira comments, instead of the `[~accountid:ACCOUNT_ID]`.

1. Go to your Jira **Site administration** page. Click on the menu icon
   ( <i class="fa fa-ellipsis-h"></i> ) under **Actions** for your
   **Jira** product, and select **Jira settings**. In the left sidebar,
   scroll down, and under **Advanced**, click **WebHooks**. Click
   **+ Create a WebHook**.

1. Set **Name** to a name of your choice, such as `Zulip`. Set
   **Status** to **Enabled**, and set **URL** to the URL generated
   above. Select the [events](#filtering-incoming-events) you'd like
   to be notified about, and click **Create**.

{end_tabs}


{!congrats.md!}

![](/static/images/integrations/jira/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [Jira's webhook guide](https://developer.atlassian.com/server/jira/platform/webhooks/)

{!webhooks-url-specification.md!}
