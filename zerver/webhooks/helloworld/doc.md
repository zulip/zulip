# Zulip Hello World integration

Learn how Zulip integrations work with this simple Hello World example!

This webhook is Zulip's official [example
integration](/api/incoming-webhooks-walkthrough).

{start_tabs}

1. The Hello World webhook will use the `test` channel, which is created
    by default in the Zulip development environment. If you are running
    Zulip in production, you should make sure that this channel exists.

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. To trigger a notification using this example webhook, you can use
    `send_webhook_fixture_message` from a [Zulip development
    environment](https://zulip.readthedocs.io/en/latest/development/overview.html):

    ```
        (zulip-server) vagrant@vagrant:/srv/zulip$
        ./manage.py send_webhook_fixture_message \
        > --fixture=zerver/tests/fixtures/helloworld/hello.json \
        > '--url=http://localhost:9991/api{{ integration_url }}?api_key=abcdefgh&stream=channel%20name;'
    ```

    Or, use curl:

    ```
    curl -X POST -H "Content-Type: application/json" -d '{ "featured_title":"Marilyn Monroe", "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe" }' http://localhost:9991/api{{ integration_url }}?api_key=abcdefgh&stream=channel%20name;
    ```

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/helloworld/001.png)

### Related documentation

{!webhooks-url-specification.md!}
