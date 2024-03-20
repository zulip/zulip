# Zulip ClickUp integration
!!! tip ""

    Note that [Zapier][1] is usually a simpler way to
    integrate ClickUp with Zulip.

Get Zulip notifications for your ClickUp space!

[1]: ./zapier
{start_tabs}
1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Download [zulip-clickup.py][2]. `Ctrl+s` or `Cmd+s` on that page should
   work in most browsers.

1. Make sure you have a working copy of [Python](https://realpython.com/installing-python/), you will need it to run the script later.

1. Collect your ClickUp **Team ID**:
    * Go to your ClickUp home. The URL should look like `https://app.clickup.com/<TEAM_ID>/home`. Note down the
    `<TEAM_ID>`.


1. Collect your ClickUp **Client ID & Client Secret** :
    1.  Go to <https://app.clickup.com/settings/team/clickup-api> and click **Create an App** button.

    1.  You will be prompted for Redirect URL(s). Enter your zulip app URL.
        e.g. `YourZulipApp.com`.

    1.  Finally, note down the **Client ID** and **Client Secret**

1. Run the `zulip-clickup.py` script in a terminal, after replacing the all caps
   arguments with the values collected above.

    ```
    python zulip-clickup.py --clickup-team-id TEAM_ID \
                            --clickup-client-id CLIENT_ID \
                            --clickup-client-secret CLIENT_SECRET
    ```

1. Follow the instructions given by the script.

    **Note**: keep watch for your browser, you will be redirected to ClickUp authorization page
{end_tabs}

[2]: https://raw.githubusercontent.com/zulip/python-zulip-api/main/zulip/integrations/clickup/zulip_clickup.py

{!congrats.md!}

![](/static/images/integrations/clickup/002.png)
### Related documentation

{!webhooks-url-specification.md!}
