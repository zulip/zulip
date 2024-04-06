See your Travis CI build notifications in Zulip!

{start_tabs}

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

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

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/travis/001.png)

### Related documentation

{!webhooks-url-specification.md!}