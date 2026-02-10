# Zulip CircleCI integration

Zulip supports integration with CircleCI and can notify you of your
job and workflow statuses. This integration currently supports using
CircleCI with GitHub, BitBucket and GitLab.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to **Project Settings** in your project on CircleCI. Select
   **Webhooks** from the list on the left, and click **Add Webhook**.

1. In the form that opens, give your webhook a name and set the
   **Receiver URL** field to the URL generated above. Choose the
   [events](#filtering-incoming-events) you'd like to be notified about,
   and click **Add Webhook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/circleci/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
