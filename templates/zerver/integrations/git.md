# Zulip Git integration

Get Zulip notifications for your Git repositories!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!download-python-bindings.md!}

1. {!create-channel.md!}

1. {!change-zulip-config-file.md!}

    Also update the value of `STREAM_NAME` to the name of your channel.

    !!! tip ""

        Customize notification branches by editing the
        `commit_notice_destination` function. By default,
        pushes to the `main`, `master`, and `test-post-receive` branches
        will result in a notification.

1. Symlink both
   `/usr/local/share/zulip/integrations/git/zulip_git_config.py`
   and `/usr/local/share/zulip/integrations/git/post-receive`
   to the `.git/hooks` directory of your Git repository.

!!! tip ""

    Use the `test-post-receive` branch to test the plugin without modifying
    your main branch.

{end_tabs}
