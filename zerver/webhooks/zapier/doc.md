Zapier supports integrations with
[hundreds of popular products](https://zapier.com/apps). Get notifications
sent by Zapier directly in Zulip.

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. Create a account on [Zapier](https://zapier.com), and click **Make a Zap!** in the upper right.

1. Trigger (Step 1): **Choose a Trigger App**, select a **Trigger**, and click **Save + Continue**.
   Follow the flow to connect your app account to Zapier.

1. Action (Step 2): Under **Choose an Action App**, select **Webhooks by Zapier**. Select
   **POST** as the **Action**, and click **Save + Continue**.

1. Set **URL** to the URL constructed above. Set **Payload Type** to `Json`.
   Add the following two fields to **Data**:

    * `topic` corresponds to the topic of a message
    * `content` corresponds to the content of a message

    Customize the `topic` and `content` fields as necessary. Click **Continue**.

1. Click **Send Test To Webhooks by Zapier** to send a test message.

**Congratulations! You're done!**
