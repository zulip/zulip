# Zulip Trello integration

Get Zulip notifications from your Trello boards!

!!! tip ""

    [Zapier](./zapier) is usually a simpler way to integrate Trello
    with Zulip.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. **Log in to Trello**, and collect the following:

    * **Board ID**: Go to your Trello board. The URL should look like
      `https://trello.com/b/<BOARD_ID>/<BOARD_NAME>`. Note down the
      `<BOARD_ID>`.

    * **API Key**: Go to <https://trello.com/1/appkey/generate>. Note down
      the key listed under **Developer API Keys**.

    * **User Token**: Under **Developer API Keys**, click on the **Token**
      link, and click **Allow**. Note down the token generated.

1.  You're now going to need to run a Trello configuration script from a
    computer (any computer) connected to the internet. It won't make any
    changes to the computer.

    Make sure you have a working copy of Python. If you're running
    macOS or Linux, you very likely already do. If you're running
    Windows you may or may not.  If you don't have Python, follow the
    installation instructions [here][1].

    !!! tip ""

        You do not need the latest version of Python; anything 2.7 or
        higher will do.

1. Download [zulip-trello.py][2].

    !!! tip ""

        <kbd>Ctrl</kbd> + <kbd>s</kbd> or <kbd>Cmd</kbd> + <kbd>s</kbd>
        on that page should work in most browsers.

1. Run the `zulip-trello` script in a terminal, after replacing the all
   caps arguments with the values collected above and the generated URL
   above.

    ```
    python zulip_trello.py --trello-board-name  TRELLO_BOARD_NAME \
                           --trello-board-id  TRELLO_BOARD_ID \
                           --trello-api-key  TRELLO_API_KEY \
                           --trello-token  TRELLO_TOKEN \
                           --zulip-webhook-url  "GENERATED_WEBHOOK_URL"
    ```

    !!! warn ""

        **Note**: Make sure that you wrap the webhook URL generated above
        in quotes when supplying it on the command-line, as shown above.

    The `zulip_trello.py` script only needs to be run once, and can be run
    on any computer with python.

1. You can delete `zulip_trello.py` from your computer if you'd like.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/trello/001.png)

### Related documentation

{!webhooks-url-specification.md!}

[1]: https://realpython.com/installing-python/
[2]: https://raw.githubusercontent.com/zulip/python-zulip-api/main/zulip/integrations/trello/zulip_trello.py
