Learn how Zulip integrations work with this simple Hello World example!

This webhook is Zulip's official [example
integration](/api/incoming-webhooks-walkthrough).

1.  The Hello World webhook will use the `test` stream, which is
    by default in the Zulip dev environment. If you are running
    Zulip in production, you should make sure that this stream exists.

1.  Next, on your {{ settings_html|safe }}, create a Hello World bot.
    the URL for the Hello World bot using the API key and
    stream name:

    `{{ api_url }}/v1/external/helloworld?api_key=abcdefgh&stream=test`

1.  To trigger a notification using this webhook, you can use
    `send_webhook_fixture_message` from a [Zulip development
    environment](https://zulip.readthedocs.io/en/latest/development/overview.html):

        (zulip-py3-venv) vagrant@debian-10:/srv/zulip$
        ./manage.py send_webhook_fixture_message \
        > --fixture=zerver/tests/fixtures/helloworld/hello.json \
        > '--url=http://localhost:9991/api/v1/external/helloworld?api_key=&lt;api_key&gt;'

    Or, use curl:

    ```
    curl -X POST -H "Content-Type: application/json" -d '{ "featured_title":"Marilyn Monroe", "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe" }' http://localhost:9991/api/v1/external/helloworld\?api_key\=&lt;api_key&gt;
    ```

{!congrats.md!}

![](/static/images/integrations/helloworld/001.png)
