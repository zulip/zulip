# Documenting an integration

Every Zulip integration must be documented in
`zerver/webhooks/mywebhook/doc.md` (or
`templates/zerver/integrations/<integration_name>.md`, for non-webhook
integrations).

Usually, this involves a few steps:

* Add text explaining all of the steps required to setup the
  integration, including what URLs to use, etc.  If there are any
  screens in the product involved, take a few screenshots with the
  input fields filled out with sample values in order to make the
  instructions really easy to follow.  For the screenshots, use a bot
  with a name like "GitHub Bot", and an email address for the bot like
  `github-bot@zulip.example.com`. Zulip's pre-defined Markdown macros
  can be used for some of these steps. See
  [Markdown macros](#markdown-macros) for further details.

* Make sure you've added your integration to
  `zerver/lib/integrations.py`; this results in your integration
  appearing on the `/integrations` page.

* You'll need to add a SVG graphic
  of your integration's logo under the
  `static/images/integrations/logos/<name>.svg`, where `<name>` is the
  name of the integration, all in lower case; you can usually find them in the
  product branding or press page. Make sure to optimize the SVG graphic by
  running `svgo -f path-to-file`.

  If you cannot find a SVG graphic of the logo, please find and include a PNG
  image of the logo instead.

* Finally, generate a message sent by the integration and take a
  screenshot of the message to provide an example message in the
  documentation. If your new integration is a webhook integration,
  you can generate such a message from your test fixtures
  using `send_webhook_fixture_message`:

  ```
  ./manage.py send_webhook_fixture_message \
       --fixture=zerver/webhooks/pingdom/fixtures/imap_down_to_up.json \
       '--url=/api/v1/external/pingdom?stream=stream_name&api_key=api_key'
  ```

  When generating the screenshot of a sample message, give your test
  bot a nice name like "GitHub Bot", use the project's logo as the
  bot's avatar, and take the screenshots showing the stream/topic bar
  for the message, not just the message body.

## Markdown macros

**Macros** are elements in the format of `{!macro.md!}` that insert common
phrases and steps at the location of the macros. Macros help eliminate
repeated content in our documentation.

The source for macros is the Markdown files under
`templates/zerver/help/include` in the
[main Zulip server repository](https://github.com/zulip/zulip). If you find
multiple instances of particular content in the documentation, you can
always create a new macro by adding a new file to that folder.

Here are a few common macros used to document Zulip's integrations:

### `{!create-stream.md!}` macro

* **About:** Recommends that users create a dedicated stream for a
  given integration. Usually the first step in setting up an integration
  or webhook.

* **Contents:**
  See [source][1].

    **Note:** `{{ integration_display_name }}` is replaced by
    [Integration.display_name][2] and `{{ recommended_stream_name }}`
    is replaced by [Integration.stream_name][3].

* **Example usage:**

    ```
    {!create-stream.md!}
    ```

* **Example rendering:**

```text
First, create the stream you would like to use for GitLab notifications,
and subscribe all interested parties to this stream. We recommend the
name gitlab.

The integration will use the default stream gitlab if no stream is
supplied in the URL; you still need to create the stream even if you
are using this default.
```

### `{!create-bot-construct-url.md!}` macro

* **About:** Instructs users to create a bot for a given integration and
  construct a webhook URL using the bot API key and stream name. The URL is
  generated automatically for every webhook by using attributes in the
  [WebhookIntegration][4] class.

* **Contents:** See [source][5].

    **Note:** If special configuration is
    required to set up the URL and you can't use this macro, be sure to use the
    `{{ api_url }}` template variable, so that your integration
    documentation will provide the correct URL for whatever server it is
    deployed on.  If special configuration is required to set the SITE
    variable, you should document that too.

* **Example usage:**

    ```
    {!create-bot-construct-url.md!}
    ```
  Usually used right after `{!create-stream!}`.

* **Example rendering:**

```text
Next, on your Zulip settings page, create a bot for GitLab. Construct
the URL for the GitLab bot using the bot API key and stream name:

https://yourZulipDomain.zulipchat.com/api/v1/external/gitlab?api_key=abcdefgh&stream=gitlab

Modify the parameters of the URL above, where api_key is the API key of
your Zulip bot, and stream is the stream name you want the notifications
sent to.
```

### `{!append-stream-name.md!}` macro

* **About:** Recommends appending `&stream=stream_name` to a URL in cases
  where supplying a stream name in the URL is optional.

* **Contents:** See [source][6].

* **Example usage:** Usually used right after `{!create-bot-construct-url.md!}`.

    ```
    {!append-stream-name.md!}
    ```

* **Example rendering:**

```
To specify the stream, you must explicitly append
`&stream=stream_name` to the end of the above URL, where
`stream_name` is the stream you want the notifications sent to.
```

### `{!append-topic.md!}` macro

* **About:** Recommends appending `&topic=my_topic` to a URL to supply
  a custom topic for webhook notification messages.

* **Contents:** See [source][7].

* **Example usage:** Usually used right after `{!create-bot-construct-url.md!}`.

    ```
    {!append-topic.md!}
    ```

* **Example rendering:**

```
To change the topic used by the bot, simply append `&topic=name`
to the end of the above URL, where `name` is your topic.
```

### `{!congrats.md!}` macro

* **About:** Inserts congratulatory lines signifying the successful setup
  of a given integration.

* **Contents:** See [source][8].

* **Example usage:** Usually used at the end of the documentation, right
  before the sample message screenshot.

    ```
    {!congrats.md!}
    ```

* **Example rendering:**

```
**Congratulations! You're done!**

Your WebhookName notifications may look like:
```

### `{!download-python-bindings.md!}` macro

* **About:** Links to Zulip's [API page](https://zulipchat.com/api/) to download
  and install Zulip's API bindings.

* **Contents:** See [source][9].

* **Example usage:** Currently mostly used in non-webhook integrations docs
  under `templates/zerver/integrations/<integration_name>.md`.

    ```
    {!download-python-bindings.md!}
    ```

* **Example rendering:**

``` text
Download and install our [Python bindings and example scripts](/api)
on the server where the IntegrationName bot will live.
```

### `{!change-zulip-config-file.md!}` macro

* **About:** Instructs users to create a bot and specify said bot's
  credentials in the config file for a given non-webhook integration.

* **Contents:** See [source][10].

* **Example usage:** Usually used in non-webhook integration docs under
  `templates/zerver/integrations/<integration_name>.md`.

    ```
    {!change-zulip-config-file.md!}
    ```

* **Example rendering:**

```
On your Zulip settings page, create a bot for Codebase.

Next, open `integrations/codebase/zulip_codebase_config.py` with your
favorite editor, and change the following lines to specify the email
address and API key for your Codebase bot:

    ZULIP_USER = "codebase-bot@example.com"
    ZULIP_API_KEY = "0123456789abcdef0123456789abcdef"
    ZULIP_SITE = "http://localhost:9991/api"
```

### `{!git-append-branches.md!}` and `{!git-webhook-url-with-branches.md!}`

* **About:** These two macros explain how to specify a list of branches
  in the webhook URL to filter notifications in our Git-related webhooks.

* **Contents:** See [git-append-branches][12] and
  [git-webhook-url-with-branches][13].

* **Example usage:** Used exclusively in Git integrations.

    ```
    {!git-append-branches.md!}
    {!git-webhook-url-with-branches.md!}
    ```

### Other useful macros

* `{!webhook-url.md!}` - Used internally by `{!create-bot-construct-url.md!}`
  to generate the webhook URL. See [source][11].

* `{!zulip-config.md!}` - Used internally by `{!change-zulip-config-file.md!}`
  to specify the lines in the config file for a non-webhook integration.
  See [source][15].

* `{!webhook-url-with-bot-email.md!}` - Used in certain non-webhook integrations
  to generate URLs of the form (see [source][14]):

    ```
    https://bot_email:bot_api_key@yourZulipDomain.zulipchat.com/api/v1/external/beanstalk
    ```
  A good example is
  [Zulip's Beanstalk integration](https://zulipchat.com/integrations/doc/beanstalk)

[1]: https://github.com/zulip/zulip/blob/master/templates/zerver/help/include/create-stream.md
[2]: https://github.com/zulip/zulip/blob/708f3a4bb19c8e823c9ea1e577d360ac4229b199/zerver/lib/integrations.py#L51
[3]: https://github.com/zulip/zulip/blob/708f3a4bb19c8e823c9ea1e577d360ac4229b199/zerver/lib/integrations.py#L55
[4]: https://github.com/zulip/zulip/blob/708f3a4bb19c8e823c9ea1e577d360ac4229b199/zerver/lib/integrations.py#L78
[5]: https://github.com/zulip/zulip/blob/master/templates/zerver/help/include/create-bot-construct-url.md
[6]: https://github.com/zulip/zulip/blob/master/templates/zerver/help/include/append-stream-name.md
[7]: https://github.com/zulip/zulip/blob/master/templates/zerver/help/include/append-topic.md
[8]: https://github.com/zulip/zulip/blob/master/templates/zerver/help/include/congrats.md
[9]: https://github.com/zulip/zulip/blob/master/templates/zerver/help/include/download-python-bindings.md
[10]: https://github.com/zulip/zulip/blob/master/templates/zerver/help/include/change-zulip-config-file.md
[11]: https://github.com/zulip/zulip/blob/master/templates/zerver/help/include/webhook-url.md
[12]: https://github.com/zulip/zulip/blob/master/templates/zerver/help/include/git-append-branches.md
[13]: https://github.com/zulip/zulip/blob/master/templates/zerver/help/include/git-webhook-url-with-branches.md
[14]: https://github.com/zulip/zulip/blob/master/templates/zerver/help/include/webhook-url-with-bot-email.md
[15]: https://github.com/zulip/zulip/blob/master/templates/zerver/help/include/zulip-config.md
