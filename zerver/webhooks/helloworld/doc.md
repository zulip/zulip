Learn how Zulip integrations work with this simple Hello World example!

The Hello World webhook will use the `test` stream, which is
created by default in the Zulip dev environment. If you are running
Zulip in production, you should make sure that this stream exists.

Next, on your {{ settings_html|safe }}, create a Hello World bot.
Construct the URL for the Hello World bot using the API key and
stream name:

`{{ api_url }}/v1/external/helloworld?api_key=abcdefgh&stream=test`


To trigger a notification using this webhook, use
`send_webhook_fixture_message` from the Zulip command line:

```
(zulip-venv)vagrant@vagrant-ubuntu-trusty-64:/srv/zulip$
./manage.py send_webhook_fixture_message \
> --fixture=zerver/fixtures/helloworld/hello.json \
> '--url=http://localhost:9991/api/v1/external/helloworld?api_key=&lt;api_key&gt;'

```

Or, use curl:

```
curl -X POST -H "Content-Type: application/json" -d '{ "featured_title":"Marilyn Monroe", "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe" }' http://localhost:9991/api/v1/external/helloworld\?api_key\=&lt;api_key&gt;

```

{!congrats.md!}

![](/static/images/integrations/helloworld/001.png)
