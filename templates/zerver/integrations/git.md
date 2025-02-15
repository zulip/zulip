# Zulip Git integration

Get Zulip notifications for your Git repositories!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!download-python-bindings.md!}

1. {!change-zulip-config-file.md!}

1. Symlink the `post-receive` hook of your Git repository by running:

    `ln -s /usr/local/share/zulip/integrations/git/post-receive .git/hooks/post-receive`

!!! tip ""

    Use the `test-post-receive` branch to test the integration without
    modifying your `main` branch.

{end_tabs}

### Configuration options

* In `/usr/local/share/zulip/integrations/{{ integration_name }}/zulip_{{ integration_name }}_config.py`,
  you can set:

    *  The channel where notifications are sent by updating the value of
        `STREAM_NAME`. By default, notifications are sent to a channel
        named "commits".

    *  Which branches send notifications when pushed by updating the
        `commit_notice_destination` function. By default, pushes to the
        `main`, `master`, and `test-post-receive` branches will result in
        notifications.

    *  The message format used in your Zulip notifications by updating the
        `format_commit_message` function.
