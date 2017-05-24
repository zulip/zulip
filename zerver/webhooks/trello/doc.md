This webhook integration for Trello is the recommended way to
integrate with Trello, and should support all the features of
the [legacy Trello cron-based integration](#trello-plugin).

{!create-stream.md!}

{!create-bot-construct-url.md!}

Trello doesn't support creating webhooks on their website; you
have to do it using their API.  So before you create a webhook,
you'll need to follow the steps below to get from Trello
an **APPLICATION_KEY**, and a **UserToken**, and to fetch
the board's **idModel**.

To generate the **APPLICATION_KEY**, open this URL in your web browser:
`https://trello.com/1/appkey/generate`.

To generate a read access token, fill in and open this URL in the browser while logged into your Trello account:
`https://trello.com/1/authorize?key=<APPLICATION_KEY>&name=Issue+Manager&expiration=never&response_type=token&scope=read`
You will receive your **UserToken**. Note it.

Within the the board URL, you can find the **TRELLO_BOARD_SHORT_ID**.
The Trello URL format is:
`https://trello.com/b/TRELLO_BOARD_SHORT_ID/boardName`.

Now you have the **APPLICATION_KEY**, **UserToken** and **TRELLO_BOARD_SHORT_ID**.
Construct this URL and open it in your web browser:
`https://api.trello.com/1/board/<TRELLO_BOARD_SHORT_ID>?key=<APPLICATION_KEY>&token=<UserToken>`
You'll receive some JSON. Within that, find the **id** value. That's your **idModel**; note it.

Now you have all the ingredients you need.  To actually create the
Trello webhook, you will need to send an `HTTP POST`
request to the trello API webhook endpoint
(`https://api.trello.com/1/tokens/<UserToken>/webhooks/?key=<APPLICATION_KEY>`)
with the following data:

```
{
"description": "Webhook for Zulip integration",
"callbackURL": "<URL_TO_ZULIP_WEBHOOK_FROM_SECOND_STEP>",
"idModel": "<ID_MODEL>",
}
```

You can do this using the `curl` program as follows:
```
curl 'https://api.trello.com/1/tokens/<UserToken>/webhooks/?key=<APPLICATION_KEY>'
-H 'Content-Type: application/json' -H 'Accept: application/json'
--data-binary $'{\n  "description": "Webhook for Zulip integration",\n  "callbackURL": "<URL_TO_ZULIP_WEBHOOK_FROM_SECOND_STEP>",\n  "idModel": "<ID_MODEL>"\n}'
--compressed
```

The response from Trello should look like:

```
{
"id": "<WEBHOOK_ID>",
"description": "Webhook for Zulip integration",
"idModel": "<ID_MODEL>",
"callbackURL": "<URL_TO_ZULIP_WEBHOOK_FROM_SECOND_STEP>",
"active": true
}
```

Congratulations! You've created a webhook and your integration is live.


When you make changes in on this board in Trello, you will
receive Zulip notifications like this:

![](/static/images/integrations/trello/001.png)
