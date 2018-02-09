Zulip supports integration with Codeship and can notify you of
your build statuses.

1. {!create-stream.md!}

2. {!create-bot-construct-url-indented.md!}

3. Next, for your project, go to **Project Settings**, click on
   **Notifications**. The URL for the **Notifications** page should
   look like the following:

    `https://codeship.com/projects/PROJECT_ID/configure_notifications`

    where `PROJECT_ID` is the ID of your project in Codeship.

4. Click on the **+ New Notification** button.

5. In the **Webhook URL** field, provide the URL constructed above:

    ![](/static/images/integrations/codeship/001.png)

    You may also supply an optional description or a specific branch
    you would like to be notified about.

6. Click **Save**.

{!congrats.md!}

![](/static/images/integrations/codeship/002.png)
