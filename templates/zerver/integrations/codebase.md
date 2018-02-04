1. First, create the streams you’d like to use for Codebase notifications. There
   will be two types of messages: commit-related updates and issue-related updates.
   After creating these streams (we suggest naming them `codebase commits` and
   `codebase issues`), make sure to subscribe all interested parties.

2. {!download-python-bindings.md!}

3. You will need your Codebase API Username. You can find it in the settings page
   of your account, under **API Credentials**.

4. {!change-zulip-config-file-indented.md!}

5. Also, edit the following Codebase credentials in `zulip_codebase_config.py`:

    ```
    CODEBASE_API_USERNAME = "zulip-inc/leo-franchi-15"
    CODEBASE_API_KEY = 0123456789abcdef0123456789abcdef
    ```

6. Before your first run of the script, you may optionally choose to configure it
   to mirror some number of hours of prior Codebase activity:

    ```
    CODEBASE_INITIAL_HISTORY_HOURS = 10
    ```

7. Now, simply run the `api/integrations/codebase/zulip_codebase_mirror` script.
   If needed, this script may be restarted, and it will automatically resume from
   when it was last running.

8. Whenever you create a new project, commit, issue, deployment, or more, you’ll
   get notifications in your selected streams with the associated information.

{!congrats.md!}

![](/static/images/integrations/codebase/001.png)
