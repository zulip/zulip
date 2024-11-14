# Zulip Git integration

Get Zulip notifications for pushes to your Git repositories!

Note that Zulip also offers integrations for [GitHub](./github),
[GitLab](./gitlab) and various other
[version control hosting services][other-integrations].

!!! warn ""

    This integration is meant to be executed on your Git server.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!download-python-bindings.md!}

1. Symlink the `post-receive` hook of your Git repository by running:

    `ln -s {{ integration_path }}/post-receive your-repo.git/hooks/post-receive`

    !!! tip ""

        The post-receive hook is triggered on every push to the repository.

1. {!change-zulip-config-file.md!}

1. Copy the config file to the same directory as the post-receive hook.

    `cp {{ config_file_path }} your-repo.git/hooks`

!!! tip ""

    Use the `test-post-receive` branch to test the integration without
    modifying your `main` branch.

{end_tabs}

### Configuration options

In `{{ config_file_path }}`, you can set:

* The channel where notifications are sent by updating the value of
  `STREAM_NAME`. By default, notifications are sent to a channel named
  "commits".

* Which branches send notifications when pushed by updating the
  `commit_notice_destination` function. By default, pushes to the `main`,
  `master`, and `test-post-receive` branches will result in notifications.

* The message format used in your Zulip notifications by updating the
  `format_commit_message` function.

[other-integrations]: ../version-control

