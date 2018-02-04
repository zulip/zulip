{!download-python-bindings.md!}

{!create-stream.md!}

{!change-zulip-config-file.md!}

You can also specify which pushes will result in notifications and to
what stream the notifications will be sent by modifying the
`commit_notice_destination` function in `zulip_git_config.py`. By
default, pushes to the `master` and `test-post-receive` branches will
result in a notification to the stream `commits`.

Save `integrations/git/zulip_git_config.py` to the `.git/hooks`
directory of your git repository.

Symlink `/usr/local/share/zulip/integrations/git/post-receive` to
the `.git/hooks` directory of your git repository.

Whenever you make a push to the `master` branch of your git repository
(or whatever you configured above), the Zulip git plugin will send an
automated notification.

{!congrats.md!}

![](/static/images/integrations/git/001.png)

**Testing**

You can test the plugin without changing your `master` branch by
pushing to the `test-post-receive` branch.
