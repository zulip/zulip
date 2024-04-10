# Zulip ClickUp integration
!!! tip ""

    Note that [Zapier][1] is usually a simpler way to
    integrate ClickUp with Zulip.

Get Zulip notifications for your ClickUp space!

{start_tabs}

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Download [zulip-clickup.py][2]. `Ctrl+s` or `Cmd+s` on that page should
   work in most browsers.

1. Make sure you have a working copy of [Python](https://realpython.com/installing-python/),
    you will need it to run the script later.

1. Collect your ClickUp **Team ID** by going to your ClickUp home view.
    The URL should look like `https://app.clickup.com/<TEAM_ID>/home`. 
    Note down the `<TEAM_ID>`.


1. Collect your ClickUp **Client ID** and **Client Secret** :
    
    - Go to <https://app.clickup.com/settings/team/clickup-api> and click **Create an App** button.

    - You will be prompted for **Redirect URL(s)**. Enter the URL for your Zulip organization.
        e.g. `YourZulipApp.com`.

    - Finally, note down the **Client ID** and **Client Secret**
    
1. Run the `zulip-clickup.py` script in a terminal, after replacing the all caps
   arguments with the values collected above.

    ```
    python zulip-clickup.py --clickup-team-id TEAM_ID \
                            --clickup-client-id CLIENT_ID \
                            --clickup-client-secret CLIENT_SECRET
    ```

1. Follow the instructions in the terminal and keep an eye on your browser as you 
    will be redirected to a ClickUp authorization page.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/clickup/002.png)
### Related documentation

{!webhooks-url-specification.md!}

[1]: ./zapier

[2]: https://raw.githubusercontent.com/zulip/python-zulip-api/main/zulip/integrations/clickup/zulip_clickup.py
