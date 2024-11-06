# Zulip Travis CI integration

See your Travis CI build notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Add the following to the bottom of your `.travis.yml` file, and push
   the change to your repository:

    ```
    notifications:
      webhooks:
        - <URL generated above>
    ```

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/travis/001.png)

{!event-filtering-additional-feature.md!}


### Related documentation

- [Travis CI's webhook documentation][1]

{!webhooks-url-specification.md!}

[1]: https://docs.travis-ci.com/user/notifications/#configuring-webhook-notifications
