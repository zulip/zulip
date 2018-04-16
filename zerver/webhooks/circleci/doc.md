Zulip supports integration with CircleCI and can notify you of
your build statuses.

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. Add the following to the bottom of your `circle.yml` file:

    ```
    notify:
      webhooks:
        - url: <URL constructed above>
    ```

    Set **url** to the URL constructed above. Push this change to your repository.

{!congrats.md!}

![](/static/images/integrations/circleci/001.png)
