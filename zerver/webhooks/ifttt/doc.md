Get notifications from every event supported by IFTTT!

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. Next, create an IFTTT Applet and select the service you'd like
   to receive notifications from as `this`. Select **Webhooks** as
   `that`. Select the **Make a web request** action.

1. Set **URL** to the URL constructed above. Set **Method** to `POST`,
   and set **Content Type** to `application/json`. Set **Body** to a
   JSON object with two parameters: `content` and `subject`, like so:

    `{"content": "message content", "subject": "message subject"}`

    You will most likely want to specify some IFTTT **Ingredients** to
    customize the subject and content of your messages. Click **Add ingredient**
    to see the available options and customize the `content` and `subject`
    parameters as necessary. Click **Create action**, and click **Finish**.

{!congrats.md!}

![](/static/images/integrations/ifttt/001.png)
