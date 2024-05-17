Get Zulip notifications for your Git repositories!

1. {!create-an-incoming-webhook.md!}

1. {!download-python-bindings.md!}

1. {!create-channel.md!}

1. {!change-zulip-config-file.md!}

    You may also need to change the value of `STREAM_NAME`.

    You can specify the branches that will be used for notifications by modifying
    the `commit_notice_destination` function. By default,
    pushes to the `main`, `master`, and `test-post-receive` branches will result in a
    notification.

1. Symlink `/usr/local/share/zulip/integrations/git/zulip_git_config.py`
   to the `.git/hooks` directory of your Git repository.

1. Symlink `/usr/local/share/zulip/integrations/git/post-receive`
   to the `.git/hooks` directory of your Git repository.

!!! tip ""

    You can test the plugin without changing your `main` branch by
    pushing to the `test-post-receive` branch.

{!congrats.md!}

![Git bot message](/static/images/integrations/git/001.png)
