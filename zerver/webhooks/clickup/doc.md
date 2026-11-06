# Zulip ClickUp integration

Get Zulip notifications for your ClickUp workspace!

!!! tip ""

    [Zapier](./zapier) is usually a simpler way to integrate ClickUp
    with Zulip.

{start_tabs}

1.  {!create-an-incoming-webhook.md!}

    When prompted, paste the ClickUp **API Token** collected below into the
    **ClickUp API integration token** field. Zulip uses it to look up
    ClickUp task and entity names to show in your notifications.

1. {!generate-webhook-url-basic.md!}

1. **Log in to ClickUp**, and collect the following:

    * **Team ID**: Go to your ClickUp home view. The URL should look like
      `https://app.clickup.com/<TEAM_ID>/home`. Note down the
      `<TEAM_ID>`.

    * **API Token**: Go to [**Settings > ClickUp API**][1]. Note down the
      token listed under **API Token**. It looks like `pk_...`.

1.  You're now going to need to run a ClickUp configuration script from a
    computer (any computer) connected to the internet. It won't make any
    changes to the computer.

    Make sure you have a working copy of Python. If you're running
    macOS or Linux, you very likely already do. If you're running
    Windows you may or may not. If you don't have Python, follow the
    installation instructions [here][2].

1. Download [zulip_clickup.py][3].

    !!! tip ""

        <kbd>Ctrl</kbd> + <kbd>S</kbd> or <kbd>Cmd</kbd> + <kbd>S</kbd>
        on that page should work in most browsers.

1. Run the `zulip_clickup.py` script in a terminal, after replacing the all
   caps arguments with the values collected above and the generated URL
   above.

    ```
    python zulip_clickup.py --clickup-team-id  CLICKUP_TEAM_ID \
                            --clickup-api-key  CLICKUP_API_TOKEN \
                            --zulip-webhook-url  "GENERATED_WEBHOOK_URL"
    ```

    !!! warn ""

        **Note**: Make sure that you wrap the webhook URL generated above
        in quotes when supplying it on the command-line, as shown above.

    The `zulip_clickup.py` script only needs to be run once, and can be run
    on any computer with python.

1. Follow the prompt in the terminal to choose which ClickUp events you'd
   like to receive notifications for.

1. You can delete `zulip_clickup.py` from your computer if you'd like.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/clickup/001.png)

### Related documentation

- [ClickUp's webhooks documentation][4]

{!webhooks-url-specification.md!}

[1]: https://app.clickup.com/settings/team/clickup-api
[2]: https://realpython.com/installing-python/
[3]: https://raw.githubusercontent.com/zulip/python-zulip-api/main/zulip/integrations/clickup/zulip_clickup.py
[4]: https://developer.clickup.com/docs/webhooks
