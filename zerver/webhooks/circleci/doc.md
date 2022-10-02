Zulip supports integration with CircleCI and can notify you of your
job and workflow statuses. This integration currently supports using
CircleCI with GitHub, BitBucket and GitLab.

1. {!create-stream.md!}

1. {!create-bot-construct-url.md!}

1. Go to your project on CircleCI and click on **Project
   Settings**. Select **Webhooks** from the list on the left.
   Click on **Add Webhook** in the menu that opens.

1. In the form that opens, give your webhook a name and set the
   **Receiver URL** field to the URL constructed above. Choose the
   desired events and click on **Add Webhook**.

{!congrats.md!}

![](/static/images/integrations/circleci/001.png)
![](/static/images/integrations/circleci/002.png)
