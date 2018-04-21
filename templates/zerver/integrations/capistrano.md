Get Zulip notifications for your Capistrano deploys!

1. {!create-a-bot-indented.md!}

1. {!download-python-bindings.md!}

1. You can now send Zulip messages by calling the `zulip-send`
   utility from your `deploy.rb` config file. Here's some example code for
   sending a Zulip notification when a deployment has completed:

``` bash
after 'deploy', 'notify:humbug'

namespace :notify do
  desc "Post a message to Zulip after deploy"
  task :humbug do
    run_locally "echo 'I just deployed to #{stage}! :tada:' | zulip-send \
    --user capistrano-bot@example.com --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5 \
    --site={{ api_url }} \
    --stream commits --subject deployments || true"
  end
end
```

The `--user` and `--api-key` should be the email and API key of the Zulip
bot created above. You can also put these values in a `~/.zuliprc` file on
your Capistrano machine. See our [API docs](/api) for instructions on
creating that file.

!!! tip ""

    You can change the `deploy` above to another step of
    your deployment process, if you'd like the notification to fire
    at a different time. See [Capistrano's Before/After Hooks page][1]
    for more information!

[1]: http://capistranorb.com/documentation/getting-started/before-after/

{!congrats.md!}

![](/static/images/integrations/capistrano/001.png)
