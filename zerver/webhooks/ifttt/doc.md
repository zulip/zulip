IFTTT supports integrations with hundreds of
[physical and digital products](https://ifttt.com/services), like
dishwashers, cars, web services, and more. Get IFTTT notifications directly
in Zulip.

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. Create an [IFTTT account](https://ifttt.com/join). Select the service you'd like
   to receive notifications from as `this`. Select **Webhooks** as
   `that`. Select the **Make a web request** action.

1. Set **URL** to the URL constructed above. Set **Method** to `POST`,
   and set **Content Type** to `application/json`. Set **Body** to a
   JSON object with two parameters: `content` and `topic`, like so:

    `{"content": "message body", "topic": "message topic"}`

    You will most likely want to specify some IFTTT **Ingredients** to
    customize the topic and content of your messages. Click **Add ingredient**
    to see the available options and customize the `content` and `topic`
    parameters as necessary. Click **Create action**, and click **Finish**.

**Congratulations! You're done!**
