{!download-python-bindings.md!}

Once you've done that, you'll use the `zulip-send` utility to
notify you when certain events happen.

Here's some example code for sending a Zulip notification after
a deployment has completed:

```bash
after 'deploy', 'notify:humbug'

namespace :notify do
  desc "Post a message to Zulip that we've deployed"
  task :humbug do
    # this will post to Zulip as the user defined in
    # ~/.zuliprc if you omit --user and --api-key
    run_locally "echo ':beers: I just deployed to #{stage}! :beers:' | zulip-send \
    --user capistrano-bot@example.com --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5 \
    --site={{ api_url }} \
    --stream commits --subject deployments || true"
  end
end
```

Some notes:

* If you prefer not to use `--user` and `--api-key` above, you
  can fill out `~/.zuliprc` on your Capistrano machine. For
  instructions on how to write that file, see
  [the API page](/api).

* You may need to change the `deploy` above to another step of
  your deployment process, if you'd like the notification to fire
  at a different time.

{!congrats.md!}

![](/static/images/integrations/capistrano/001.png)

###### Thanks to Wes of TurboVote for [submitting this integration][1]!

[1]: https://gist.github.com/cap10morgan/5100822
