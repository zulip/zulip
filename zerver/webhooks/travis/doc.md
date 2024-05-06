See your Travis CI build notifications in Zulip!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}
   By default, pull request events are ignored since most people
   don't want notifications for new pushes to pull requests.  To
   enable notifications for pull request builds, just
   append `&ignore_pull_requests=false` to the end of the URL.

1. Add the following to the bottom of your `.travis.yml` file:

    ```
    notifications:
      webhooks:
        - <URL constructed above>
    ```

    Push this change to your repository. To further configure which
    specific events should trigger a notification, see
    [Travis CI's webhook documentation][1].

[1]: https://docs.travis-ci.com/user/notifications/#Configuring-webhook-notifications

{!congrats.md!}

![](/static/images/integrations/travis/001.png)
