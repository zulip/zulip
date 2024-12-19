# Zulip Jira integration

Get Zulip notifications for your Jira projects!

!!! warn ""

      **Note**: These instructions apply to Atlassian Cloud's hosted Jira, and Jira
      Server versions 5.2 or greater. For older versions, you'll need our
      [Jira plugin](./jira-plugin).

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

      To include a mentioned user's display name in your Jira notifications,
      add `&email=YOUR_JIRA_EMAIL` and `&jira_api_token=JIRA_API_
      TOKEN` to the generated URL. For instructions on generating your
      `JIRA_API_TOKEN`, refer to this [Jira documentation][1].
      Otherwise, it will appear as `[~accountid:6420c1740152b5f4f9f28a08]`
      in Zulip.

1. Go to your Jira **Site administration** page. Click on the menu icon
   ( <i class="fa fa-ellipsis-h"></i> ) under **Actions** for your
   **Jira** product, and select **Jira settings**. In the left sidebar,
   scroll down, and under **Advanced**, click **WebHooks**. Click
   **+ Create a WebHook**.

1. Set **Name** to a name of your choice, such as `Zulip`. Set
   **Status** to **Enabled**, and set **URL** to the URL generated
   above. Select the [events][2] you'd like
   to be notified about, and click **Create**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/jira/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [Jira's webhook guide](https://developer.atlassian.com/server/jira/platform/webhooks/)

{!webhooks-url-specification.md!}

[1]: https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/
[2]: #filtering-incoming-events
