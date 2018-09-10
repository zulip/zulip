Get Zulip notifications from your Trello boards!

!!! tip ""
    Note that [the Zapier integration][1] is usually a simpler way to
    integrate Trello with Zulip.

[1]: ./zapier

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. We will first collect three items: a **Board ID**, an **API Key**, and a
   **User Token**.

    * **Board ID**: Go to your Trello board. The URL should look like
      `https://trello.com/b/<BOARD_ID>/<BOARD_NAME>`. Note down the
      `<BOARD_ID>`.

    * **API Key**: Go to <https://trello.com/1/appkey/generate>. Note down the
      key listed under **Developer API Keys**.

    * **User Token**: Go to <https://trello.com/1/appkey/generate>. Under
      **Developer API Keys**, click on the **Token** link. Click on **Allow**.
      Note down the token generated.

1. Download and install our
   [Python bindings and example scripts](/api/installation-instructions).

    Trello supports outgoing webhooks, but unfortunately, doesn't have a UI
    for configuring them. Instead, you have to use the Trello API to create
    webhooks. We have provided a convenient script for doing this with the
    Trello API in the Zulip Python bindings. You'll need to run this script
    once on any machine (it doesn't have to be your Zulip server) to setup
    the webhook; after you've done that, Trello will send the notifications
    directly to your Zulip server.

1. Open `/usr/local/share/zulip/integrations/trello/zulip_trello_config.py`
   with your favorite editor and change the following lines to specify
   the Trello **API Key**, **User Token**, and the webhook URL constructed
   above:

    ```
    TRELLO_API_KEY = "<Trello API key generated above>"
    TRELLO_TOKEN = "<Trello User Token generated above>"
    ZULIP_WEBHOOK_URL = "<URL constructed above>"
    ```

1. Go to the `/usr/local/share/zulip/integrations/trello/` directory
   and run the `zulip_trello.py` script, like so:

    ```
    python zulip_trello.py <trello_board_name> <trello_board_id>
    ```

    Replace `<trello_board_name` and `<trello_board_id>` with the Trello
    board's name and **Board ID**, respectively.

    The `zulip_trello.py` script needs to be run only once to register
    the webhook, and can be run from any machine.

!!! tip ""
    To learn more, see [Trello's webhooks documentation][2].

[2]: https://developers.trello.com/page/webhooks

{!congrats.md!}

![](/static/images/integrations/trello/001.png)
