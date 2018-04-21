Get Zulip notifications for your Git repositories!

1. {!create-a-bot-indented.md!}

1. {!download-python-bindings.md!}

1. {!create-stream.md!}

1. {!change-zulip-config-file-indented.md!}

    To specify a different stream, simply change the value of `STREAM_NAME` in
    `zulip_git_config.py` to the name of the stream you'd like to use.

1. Symlink `/usr/local/share/zulip/integrations/git/zulip_git_config.py`
   to the `.git/hooks` directory of your git repository. Symlink
   `/usr/local/share/zulip/integrations/git/post-receive` to
   the `.git/hooks` directory of your git repository.

!!! tip ""

    You can specify the branches that will be used for notifications by modifying
    the `commit_notice_destination` function in `zulip_git_config.py`. By default,
    pushes to the `master` and `test-post-receive` branches will result in a
    notification to the stream `commits`.

!!! tip ""

    You can test the plugin without changing your `master` branch by
    pushing to the `test-post-receive` branch.

{!congrats.md!}

![](/static/images/integrations/git/001.png)
