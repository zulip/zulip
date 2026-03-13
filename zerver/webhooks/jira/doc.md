# Zulip Jira integration

Get Zulip notifications for your Jira projects!

!!! tip ""

    If you also configure a [custom profile
    field](/help/custom-profile-fields) for Atlassian account IDs,
    this integration will refer to Jira users using [Zulip silent
    mentions](/help/mention-a-user-or-group#silently-mention-a-user),
    rather than their Jira display name. See [how to find Atlassian
    account IDs][atlassian-account-id].

[atlassian-account-id]: https://developer.atlassian.com/cloud/automation/resources/how-to-get-user-account-IDs/

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

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
