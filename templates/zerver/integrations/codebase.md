# Zulip Codebase integration

Get Codebase notifications in Zulip!

{start_tabs}

1. [Create the channels](/help/create-a-channel) you’d like to use for
   Codebase notifications. There will be two types of notification
   messages: issue-related and commit-related.

1. {!create-an-incoming-webhook.md!}

1. {!download-python-bindings.md!}

1.  Install the requirements for the integration script with:

    `pip install /usr/local/share/zulip/integrations/codebase/requirements.txt`

1. {!change-zulip-config-file.md!}

    Also add `ZULIP_TICKETS_STREAM_NAME` and `ZULIP_COMMITS_STREAM_NAME`
    with the names of the channels you created in step 1.

1. Go to your Codebase settings, and click on **My Profile**. Under
   **API Credentials**, you will find your API key and username.
   Edit the following lines in `zulip_codebase_config.py` to add your
   Codebase credentials:

    ```
    CODEBASE_API_USERNAME = "zulip-inc/user-name-123"
    CODEBASE_API_KEY = 0123456789abcdef0123456789abcdef
    ```

    !!! tip ""

        Before your first run of the script, you may also want to configure
        the integration to mirror some number of hours of prior Codebase
        activity, e.g., `CODEBASE_INITIAL_HISTORY_HOURS = 10`.

1. Run the
   `/usr/local/share/zulip/integrations/codebase/zulip_codebase_mirror`
   script.

    !!! tip ""

        This script can be restarted, and it will resume from when it was
        last running.

{end_tabs}

{!congrats.md!}

![Codebase bot message](/static/images/integrations/codebase/001.png)
