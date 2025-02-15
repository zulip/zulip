# Zulip Git integration

Get Zulip notifications for your Git repositories!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!download-python-bindings.md!}

1. {!change-zulip-config-file.md!}

    To customize further, refer to the
    [configuration options](#configuration-options).

1. Symlink the `post-receive` hook of your Git repository by running:

    `ln -s /usr/local/share/zulip/integrations/git/post-receive .git/hooks/post-receive`

!!! tip ""

    Use the `test-post-receive` branch to test the plugin without modifying
    your main branch.

{end_tabs}

### Configuration options

The configuration file `/usr/local/share/zulip/integrations/{{ integration_name }}/zulip_{{ integration_name }}_config.py` supports the following options.

*  By default, the notifications are sent to a channel named "commits".
   To configure it, edit `STREAM_NAME`.

    `STREAM_NAME = <Name of the channel where messages should be sent>`

*  Customize notification branches by editing the
   `commit_notice_destination` function. By default, pushes to the `main`,
   `master`, and `test-post-receive` branches will result in a notification.

*  Configure the commit message format used in your Zulip notifications by
   editing the `format_commit_message` function.
