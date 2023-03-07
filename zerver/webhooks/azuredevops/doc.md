Get Azure Devops notifications in Zulip!

1. {!create-stream.md!}

1. {!create-bot-construct-url.md!}

    {!git-webhook-url-with-branches.md!}

1. Go to your project on Azure DevOps and click on the **Project
   settings** in the bottom left corner. Select **Service
   hooks**. Click on **Create subscription**. Select **Web hooks** and
   then **Next**.

1. Select the events you would like to receive notifications for and
   then click **Next**. This integration supports the following
   events:
    * Code pushed
    * Pull request created
    * Pull request updated
    * Pull request merge attempted

1. Set **URL** to the URL constructed above. Ensure that **Resource
   details to send** and **Detailed messages to send** are set to
   **All**. Click **Finish**.

{!congrats.md!}

![](/static/images/integrations/azuredevops/001.png)
