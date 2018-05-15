Get Codebase notifications in Zulip!

1. First, create the streams you’d like to use for Codebase notifications. There
   will be two types of messages: commit-related updates and issue-related
   updates. We recommend naming the streams `codebase` and `tickets` for
   commit-related updates and issue-related updates, respectively. After
   creating these streams, make sure to subscribe all interested parties.

1. {!create-a-bot-indented.md!}

1. {!download-python-bindings.md!}

1. {!change-zulip-config-file-indented.md!}

    To specify a different stream for issue-related updates, simply change the
    value of `ZULIP_TICKETS_STREAM_NAME` to the name of the stream you'd like
    to use.

    To specify a different stream for commit-related updates, simply change the
    value of `ZULIP_COMMITS_STREAM_NAME` to the name of the stream you'd like
    to use.

    Go to your account's settings, and click on **My Profile**. Under
    **API Credentials**, you will find your API key and username. Now, you can
    edit the following Codebase credentials in `zulip_codebase_config.py`:

    ```
    CODEBASE_API_USERNAME = "zulip-inc/leo-franchi-15"
    CODEBASE_API_KEY = 0123456789abcdef0123456789abcdef
    ```

    You may also choose to configure this integration to mirror some number
    of hours of prior Codebase activity:

    ```
    CODEBASE_INITIAL_HISTORY_HOURS = 10
    ```

1. Run the `/usr/local/share/zulip/integrations/codebase/zulip_codebase_mirror`
   script. If needed, this script may be restarted, and it will automatically
   resume from when it was last running.

{!congrats.md!}

![](/static/images/integrations/codebase/001.png)
