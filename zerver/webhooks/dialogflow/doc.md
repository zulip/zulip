Get personal message notifications in Zulip for the results of your
Dialogflow queries!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

    The API key for an incoming webhook bot cannot be used to read messages out
    of Zulip. Thus, using an incoming webhook bot lowers the security risk of
    exposing the bot's API key to a third-party service.

    Construct the URL for the Dialogflow bot using the bot's API key and your
    Zulip email. The webhook URL should look like:

    `{{api_url}}?api_key=BOT'S_API_KEY&email=foo@example.com`

    Modify the parameters of the URL above where `api_key` is the API key of your Zulip bot
    and `email` is your Zulip email.

1. Go to the **Fulfillment** settings of your Dialogflow app and enable **Webhooks**.
   Set **URL** to the URL constructed above.
   Go to **Intents** and at the bottom, check the box **Use webhook**
   under **Fulfillment**.

{!congrats.md!}

![](/static/images/integrations/dialogflow/001.png)
