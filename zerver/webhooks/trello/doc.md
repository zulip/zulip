!!! tip ""

    Note that [Zapier][1] is usually a simpler way to
    integrate Trello with Zulip.

Get Zulip notifications from your Trello boards!

[1]: ./zapier

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. **Log in to Trello**, and collect the following three items:

    * **Board ID**: Go to your Trello board. The URL should look like
      `https://trello.com/b/<BOARD_ID>/<BOARD_NAME>`. Note down the
      `<BOARD_ID>`.

    * **API Key**: Go to <https://trello.com/1/appkey/generate>. Note down the
      key listed under **Developer API Keys**.

    * **User Token**: Go to <https://trello.com/1/appkey/generate>. Under
      **Developer API Keys**, click on the **Token** link. Click on **Allow**.
      Note down the token generated.

    You're now going to need to run a Trello configuration script from a
    computer (any computer) connected to the internet. It won't make any
    changes to the computer.

1. Make sure you have a working copy of Python. If you're running
    macOS or Linux, you very likely already do. If you're running
    Windows you may or may not.  If you don't have Python, follow the
    installation instructions
    [here](https://realpython.com/installing-python/). Note that you
    do not need the latest version of Python; anything 2.7 or higher
    will do.

1. Download [zulip-trello.py][2]. `Ctrl+s` or `Cmd+s` on that page should
   work in most browsers.

1. Run the `zulip-trello` script in a terminal, after replacing the all caps
   arguments with the values collected above.

    ```
    python zulip_trello.py --trello-board-name  TRELLO_BOARD_NAME \
                           --trello-board-id  TRELLO_BOARD_ID \
                           --trello-api-key  TRELLO_API_KEY \
                           --trello-token  TRELLO_TOKEN \
                           --zulip-webhook-url  "ZULIP_WEBHOOK_URL"
    ```

    **Note**: Make sure that you wrap the webhook URL in quotes
    when supplying it on the command-line, as shown above.

    The `zulip_trello.py` script only needs to be run once, and can be run
    on any computer with python.

1. You can delete `zulip_trello.py` from your computer if you'd like.

[2]: https://raw.githubusercontent.com/zulip/python-zulip-api/main/zulip/integrations/trello/zulip_trello.py

{!congrats.md!}

![](/static/images/integrations/trello/001.png)
