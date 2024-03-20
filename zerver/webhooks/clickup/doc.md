!!! tip ""

    Note that [Zapier][1] is usually a simpler way to
    integrate ClickUp with Zulip.

Get Zulip notifications from your ClickUp space!

[1]: ./zapier

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

    You're now going to need to run a ClickUp Integration configuration script from a
    computer (any computer) connected to the internet. It won't make any
    changes to the computer.
    
1. Make sure you have a working copy of Python. If you're running
    macOS or Linux, you very likely already do. If you're running
    Windows you may or may not.  If you don't have Python, follow the
    installation instructions
    [here](https://realpython.com/installing-python/). Note that you
    do not need the latest version of Python; anything 2.7 or higher
    will do.
1. Download [zulip-clickup.py][2]. `Ctrl+s` or `Cmd+s` on that page should
   work in most browsers.

1. To run the script, you require the following 3 items:

    * **Team ID**: Go to your ClickUp home. The URL should look like
      `https://app.clickup.com/<TEAM_ID>/home`. Note down the
      `<TEAM_ID>`.

    * **Client ID & Client Secret**: Please follow the instructions below:
        
        - Go to <https://app.clickup.com/settings/team/clickup-api> and click **Create an App** button.

        - After that, you will be prompted for Redirect URL(s). You must enter your zulip app URL.
            e.g. `YourZulipApp.com`. 

        - Finally, note down the **Client ID** and **Client Secret**

1. Run the `zulip-clickup` script in a terminal, after replacing the all caps
   arguments with the values collected above.

    ```
    python zulip-clickup.py --clickup-team-id TEAM_ID \
                            --clickup-client-id CLIENT_ID \
                            --clickup-client-secret CLIENT_SECRET
    ```
    
    The `zulip-clickup.py` script only needs to be run once, and can be run
    on any computer with python.

1. Follow the instructions given by the script. 
    **Note:** You will be prompted for the **integration url** you just generated in step 2 and watch your browser since you will be redirected to a ClickUp authorization page to proceed.

1. You can delete `zulip-clickup.py` from your computer if you'd like or run it again to 
    reconfigure your ClickUp integration.

[2]: https://raw.githubusercontent.com/zulip/python-zulip-api/main/zulip/integrations/trello/zulip_trello.py

{!congrats.md!}

![](/static/images/integrations/clickup/001.png)
