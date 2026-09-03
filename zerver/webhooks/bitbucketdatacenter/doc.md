# Zulip Bitbucket Data Center integration

Receive Bitbucket Data Center notifications in Zulip!

Zulip supports both Git and Mercurial notifications from Bitbucket.

For Bitbucket Cloud, the service hosted at bitbucket.org, see the
[Bitbucket integration](./bitbucket) instead.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-with-branch-filtering.md!}

1. On your repository's web page, go to **Settings**. Select
   **Webhooks**, and then click **Add webhook**.

    !!! tip ""

        To get notifications for every repository in a project, create
        the webhook in that project's **Project settings** instead.

1. Set **Title** to a title of your choice, such as `Zulip`. Set **URL**
   to the URL generated above, and toggle the **Active** checkbox.
   Select the **Triggers** you'd like to be notified about, and click
   **Save**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/bitbucketdatacenter/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [Bitbucket Data Center's webhook documentation][bitbucket-webhooks]

{!webhooks-url-specification.md!}

[bitbucket-webhooks]: https://confluence.atlassian.com/bitbucketserver/manage-webhooks-938025878.html
