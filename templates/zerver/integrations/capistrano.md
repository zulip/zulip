# Zulip Capistrano Integration

Get Zulip notifications for your Capistrano deploys!

{start_tabs}

1.  {!create-an-incoming-webhook.md!}

1.  {!download-python-bindings.md!}

1.  You can now send Zulip messages by calling the `zulip-send`
    utility from your `deploy.rb` config file.

1. Here's some example code for sending a Zulip notification when a
   deployment has completed:

        after 'deploy', 'notify:humbug'

        namespace :notify do
          desc "Post a message to Zulip after deploy"
          task :humbug do
            run_locally "echo 'I just deployed to #{stage}! :tada:' | zulip-send \
            --user capistrano-bot@{{ display_host }} --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5 \
            --site={{ zulip_url }} \
            --stream commits --subject deployments || true"
          end
        end

    Use your bot's email address and [API key][3] for `--user` and
    `--api-key` respectively.

{end_tabs}

{!congrats.md!}

![Capistrano bot message](/static/images/integrations/capistrano/001.png)

### Configuration Options

* Customize the notification trigger by replacing `deploy` in the above
  example with [any stage][1] of your deployment process.

### Related documentation

* [Capistrano's Before/After Hooks][1]
* [Configuring the Python bindings][2]

[1]: https://capistranorb.com/documentation/getting-started/before-after/
[2]: https://zulip.com/api/configuring-python-bindings
[3]: https://zulip.com/api/api-keys#get-a-bots-api-key
