Get Zulip notifications from your Trello boards!

!!! tip ""
    Note that [the Zapier integration][1] is usually a simpler way to
    integrate Trello with Zulip.

[1]: ./zapier

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. Log in to Trello, and collect the following three items:

    * **Board ID**: Go to your Trello board. The URL should look like
      `https://trello.com/b/<BOARD_ID>/<BOARD_NAME>`. Note down the
      `<BOARD_ID>`.

    * **API Key**: Go to <https://trello.com/1/appkey/generate>. Note down the
      key listed under **Developer API Keys**.

    * **User Token**: Go to <https://trello.com/1/appkey/generate>. Under
      **Developer API Keys**, click on the **Token** link. Click on **Allow**.
      Note down the token generated.

1. Trello supports outgoing webhooks, but unfortunately, doesn't have a UI
    for configuring them. Instead, you have to use the Trello API to create
    webhooks. We have provided a convenient script for doing this, which you can
    download [here][2].

    You'll need Python to run the script. You'll need
    to run this script once on any machine (it doesn't have to be your Zulip
    server) to setup the webhook; after you've done that, Trello will send
    the notifications directly to your Zulip server.

    !!! tip ""
        If you don't have Python installed on your machine, follow
        [these installation instructions](https://realpython.com/installing-python/)
        for your OS.

1. Execute the `zulip-trello` script with the requisite arguments:

    ```
    python zulip_trello.py --trello-board-name <trello_board_name> \
                           --trello-board-id   <trello_board_id> \
                           --trello-api-key  <trello_api_key> \
                           --trello-token <trello_token> \
                           --zulip-webhook-url <zulip_webhook_url>
    ```

    Replace the arguments above with your Trello credentials and the
    webhook URL constructed above.

    The `zulip_trello.py` script needs to be run only once to register
    the webhook, and can be run from any machine.

!!! tip ""
    To learn more, see [Trello's webhooks documentation][3].

[2]: https://raw.githubusercontent.com/zulip/python-zulip-api/master/zulip/integrations/trello/zulip_trello.py
[3]: https://developers.trello.com/page/webhooks

{!congrats.md!}

![](/static/images/integrations/trello/001.png)
