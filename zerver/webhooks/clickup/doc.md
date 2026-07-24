# Zulip ClickUp integration

Get Zulip notifications for your ClickUp space!

!!! tip ""

    [Zapier](./zapier) is usually a simpler way to integrate ClickUp
    with Zulip.

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Collect your ClickUp **Team ID** by going to your ClickUp home view.
    The URL should look like `https://app.clickup.com/<TEAM_ID>/home`.
    Note down the `<TEAM_ID>`.

1. Collect your ClickUp **Client ID** and **Client Secret** by following these steps:

    - Go to your [ClickUp API menu][1] and click **Create an App**.

    - You will be prompted for **Redirect URL(s)**, enter the URL for your Zulip organization.
        e.g., `{{ zulip_url }}`.

    - Note down the **Client ID** and **Client Secret**

1.  You're now going to need to run a ClickUp configuration script from a
    computer (any computer) connected to the internet. It won't make any
    changes to the computer.

    Make sure you have a working copy of Python. If you're running
    macOS or Linux, you very likely already do. If you're running
    Windows you may or may not.  If you don't have Python, follow the
    installation instructions [here][2].

    !!! tip ""

        You do not need the latest version of Python; anything 2.7 or
        higher will do.

1. Download [zulip-clickup.py][3].

    !!! tip ""

        <kbd>Ctrl</kbd> + <kbd>s</kbd> or <kbd>Cmd</kbd> + <kbd>s</kbd>
        on that page should work in most browsers.

1. Run the `zulip-clickup.py` script in a terminal, after replacing the all caps
   arguments with the values collected above.

    ```
    python zulip-clickup.py --clickup-team-id CLICKUP_TEAM_ID \
                            --clickup-client-id CLICKUP_CLIENT_ID \
                            --clickup-client-secret CLICKUP_CLIENT_SECRET \
                            --zulip-webhook-url "ZULIP_WEBHOOK_URL"
    ```

    !!! warn ""

        **Note**: Make sure that you wrap the webhook URL generated above
        in quotes when supplying it on the command-line, as shown above.

1. Follow the instructions in the terminal and keep an eye on your browser as you
   will be redirected to a ClickUp authorization page.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/clickup/001.png)

### Related documentation

- [Zapier ClickUp integration][4]

{!webhooks-url-specification.md!}

[1]: https://app.clickup.com/settings/team/clickup-api

[2]: https://realpython.com/installing-python/

[3]: https://raw.githubusercontent.com/zulip/python-zulip-api/main/zulip/integrations/clickup/zulip_clickup.py

[4]: https://zapier.com/apps/clickup/integrations#zap-template-list
