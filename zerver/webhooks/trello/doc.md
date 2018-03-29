### Get Zulip notifications from your Trello boards!

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

1. {!download-python-bindings.md!}

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

    Replace `<trello_board_name` and `<trello_board_id` with the Trello
    board's name and **Board ID**, respectively.

!!! tip ""
    To learn more, see [Trello's webhooks documentation][1].

[1]: https://developers.trello.com/page/webhooks

{!congrats.md!}

![](/static/images/integrations/trello/001.png)
