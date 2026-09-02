# Zulip Bitbucket integration

Receive Bitbucket Cloud notifications in Zulip!

Zulip supports both Git and Mercurial notifications from Bitbucket.

!!! warn ""

    For Bitbucket Data Center webhooks, see the [Zulip Bitbucket
    Data Center](/integrations/bitbucketdatacenter) integration.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-with-branch-filtering.md!}

1. On your repository's web page, go to **Settings**. Select
   **Webhooks**, and then click **Add webhook**.

1. Set **Title** to a title of your choice, such as `Zulip`. Set **URL**
   to the URL generated above, and toggle the **Active** checkbox.
   Select the **Triggers** you'd like to be notified about, and click
   **Save**.

{end_tabs}

!!! tip ""

    If you configure a [custom profile field](/help/custom-profile-fields)
    in your Zulip organization for Atlassian Cloud account IDs,
    this integration will refer to Bitbucket users using
    [Zulip silent mentions](/help/mention-a-user-or-group#silently-mention-a-user),
    rather than their Bitbucket display name. See [how to find Atlassian
    account IDs][atlassian-account-id].

[atlassian-account-id]: https://developer.atlassian.com/cloud/automation/resources/how-to-get-user-account-IDs/

{!congrats.md!}

![](/static/images/integrations/bitbucket/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
