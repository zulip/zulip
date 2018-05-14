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
  `github-bot@zulip.example.com`. For more detailed writing guidelines, see
  [Writing guidelines](#writing-guidelines).

    Zulip's pre-defined Markdown macros
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

* `{!create-stream.md!}` macro - Recommends that users create a dedicated
  stream for a given integration. Usually the first step in setting up an
  integration or webhook. For an example rendering, see **Step 1** of
  [the docs for Zulip's GitHub integration][GitHub].

* `{!create-bot-construct-url.md!}` macro - Instructs users to create a bot
  for a given integration and construct a webhook URL using the bot API key
  and stream name. The URL is generated automatically for every webhook by using
  attributes in the [WebhookIntegration][1] class.
  This macro is usually used right after `{!create-stream!}`. For an example
  rendering, see **Step 2** of [the docs for Zulip's GitHub integration][GitHub].

    **Note:** If special configuration is
    required to set up the URL and you can't use this macro, be sure to use the
    `{{ api_url }}` template variable, so that your integration
    documentation will provide the correct URL for whatever server it is
    deployed on.  If special configuration is required to set the `SITE`
    variable, you should document that too.

* `{!append-stream-name.md!}` macro - Recommends appending `&stream=stream_name`
  to a URL in cases where supplying a stream name in the URL is optional.
  Supplying a stream name is optional for most Zulip integrations. If you use
  `{!create-bot-construct-url.md!}`, this macro need not be used.

* `{!append-topic.md!}` macro - Recommends appending `&topic=my_topic` to a URL
  to supply a custom topic for webhook notification messages. Supplying a custom
  topic is optional for most Zulip integrations. If you use
  `{!create-bot-construct-url.md!}`, this macro need not be used.

* `{!congrats.md!}` macro - Inserts congratulatory lines signifying the
  successful setup of a given integration. This macro is usually used at
  the end of the documentation, right before the sample message screenshot.
  For an example rendering, see the end of
  [the docs for Zulip's GitHub integration][GitHub].

* `{!download-python-bindings.md!}` macro - Links to Zulip's
  [API page](https://zulipchat.com/api/) to download and install Zulip's
  API bindings. This macro is usually used in non-webhook integration docs under
  `templates/zerver/integrations/<integration_name>.md`. For an example
  rendering, see **Step 2** of
  [the docs for Zulip's Codebase integration][codebase].

* `{!change-zulip-config-file.md!}` macro - Instructs users to create a bot and
  specify said bot's credentials in the config file for a given non-webhook
  integration. This macro is usually used in non-webhook integration docs under
  `templates/zerver/integrations/<integration_name>.md`. For an example
  rendering, see **Step 4** of
  [the docs for Zulip's Codebase integration][codebase].

* `{!git-append-branches.md!}` and `{!git-webhook-url-with-branches.md!}` -
  These two macros explain how to specify a list of branches in the webhook URL
  to filter notifications in our Git-related webhooks. For an example rendering,
  see the last paragraph of **Step 2** in
  [the docs for Zulip's GitHub integration][GitHub].

* `{!webhook-url.md!}` - Used internally by `{!create-bot-construct-url.md!}`
  to generate the webhook URL.

* `{!zulip-config.md!}` - Used internally by `{!change-zulip-config-file.md!}`
  to specify the lines in the config file for a non-webhook integration.

* `{!webhook-url-with-bot-email.md!}` - Used in certain non-webhook integrations
  to generate URLs of the form:

    ```
    https://bot_email:bot_api_key@yourZulipDomain.zulipchat.com/api/v1/external/beanstalk
    ```

    For an example rendering, see
    [Zulip's Beanstalk integration](https://zulipchat.com/integrations/doc/beanstalk).

[GitHub]: https://zulipchat.com/integrations/doc/github
[codebase]: https://zulipchat.com/integrations/doc/codebase
[beanstalk]: https://zulipchat.com/integrations/doc/beanstalk
[1]: https://github.com/zulip/zulip/blob/708f3a4bb19c8e823c9ea1e577d360ac4229b199/zerver/lib/integrations.py#L78

## Writing guidelines

For the vast majority of integrations, you should just copy the docs for a
similar integration and edit it. [Basecamp][basecamp] is a good one to copy.

[basecamp]: https://zulipchat.com/integrations/doc/basecamp

### General writing guidelines

At at high level, the goals are for the instructions to feel simple, be easy to
follow, and be easy to maintain. Easier said than done, but here are a few
concrete guidelines.

##### Feel simple

- Use simple language.
- Use the imperative tense.
- Only describe things as much as necessary. For example: “Click on
  **Settings.** Select **Project settings**.” is better than “Click on
  **Settings**. Select **Project settings** from the dropdown.”
- Cut unnecessary words. For example, do not start steps with transition words
  like “Next”, “First”, “Second”, “Now”, etc. Each step should be structurally
  independent.

##### Be easy to follow

- Actions should appear in order, including implicit ones. So “Under
  **Webhooks**, click **Add Webhook**.” not “Click **Add Webhook** in the
  **Webhooks** section.” “Under Webhooks” is an action, since it’s basically
  the same as “Find the Webhooks section”.
- UI elements in third-party websites should be **bolded**.
- Trailing punctuation can be stripped from bolded elements. For example,
  “**Enable this checkbox**" instead of “**Enable this checkbox?**".
  Starting punctuation such as the “**+**" in “**+ New Notification**" should
  be preserved.
- You can use a screenshot if a step is particularly complicated (see below).

##### Be easy to maintain

- Follow the organization and wording of existing docs as much as possible.


### Guidelines for specific steps

Most `doc.md` files should start with a generic sentence about the
integration, for example, “Get webhook_name notifications in Zulip!”, where
`webhook_name` is the name of the integration. This sentence can also be
tailored to the integration in question. All instructions should be organised
into numbered steps.

##### "Create the stream" step

- Use the `create-stream` macro. This step should be omitted if the
  integration only supports notifications via PMs. You can find the list of
  all such macros [here](#markdown-macros).

##### “Create the bot” step

- Use the `create-bot-construct-url` macro. You can find the list of all such
  macros [here](#markdown-macros).
- Existing macros should be used for this if they exist, but if the macro
  defaults don’t work, it may make sense to write something custom for the
  integration in question. This step is mandatory for all integrations.

##### “Navigate to this screen” step

- In general, this should be one step, even if it takes multiple clicks.
- Begin by mentioning the third-party service being documented with language
  such as “Go to your Taiga project”, “Go to your GitHub repository”,
  “On your X project”, etc. Assume the user is already logged in to their
  account.
- If a UI element is difficult to spot, you can use additional cues like
  “Click on **Settings** in the top-right corner” or “On the left, click
  **Webhooks**.”. Only do this if the element is actually difficult to spot.
- If this step includes more than 5 sentences, it may need to be split up
  into multiple steps.

##### “Fill out form and save” step

- Filling out a form and clicking **Save** should generally be one step, even if
  there are multiple fields to fill out.
- It’s fine to say things like “Follow the on-screen instructions to create an
  app” if they have a sequence of steps they guide you through that are pretty
  clear.

Lastly, end with the `congrats.md` macro and a screenshot of a sample message
within Zulip.

### Screenshots

Screenshots are hard to maintain, so we generally err on the side of not
including screenshots. That being said, screenshots may be used to aid the
process if the third-party UI is confusing or a specific UI element is hard
to find. A few things to keep in mind:

- Screenshots should be small and should mainly include the third-party UI that
  the text is referring to that is difficult to locate.
- Screenshots should never include the entirety of a third-party website’s page.
- Each screenshot should be preceded by the step that refers to it. For example,
  “3. Click on **hard-to-find-button:** <screenshot showing the hard-to-find-button goes on the next line>".

### Language and style

- For Step 2 and 3, if custom text is required, try to see if there is another
  integration that has language you can copy.
- For navigational instructions:
    - All instructions must follow the format “Click on **X**”, where **X** is the
      third-party UI element to be clicked.
    - Text that refers to a UI element in a third-party website must always be
      bolded.
    - If a UI element is difficult to spot, additional cues may be used such as
      “Click on **X** in the top-right corner”.
    - Slight variations such as “Select **X**" instead of “Click **X**" are
      acceptable if they make the language flow better.
    - For check-boxes, consider wording like “Check the **Y** checkbox” or “Check
      the **Y** option” or “Check the box labelled **Y**”. Additional cues such as
      “Under the **X** section, check the **Y** checkbox” can also work.
    - “Go to the Dashboard, and select X” is preferred over language such as “On
      the Dashboard, select X”. The second sentence is harder to parse, especially
      if “Dashboard” or “X” are complicated themselves.
    - Avoid sentences like “for the project you’d like to receive notifications
      for”, since they make sentences unnecessarily complicated, and don’t add
      much content.
- For form-related instructions:
    - To set a specific field, instructions must follow the format “Set **URL**
      to the URL constructed above”.
    - Text that refers to a UI element in a third-party website must always be
      bolded.
- Wherever necessary, steps may be prefixed by instructions such as “Go to your
  repository’s webpage” or “Go to your project’s dashboard”, as appropriate.
- Additional cues such as “Select **X** from the drop-down menu” are also
  acceptable.

### Other considerations

- Where additional cues are necessary (due to confusing UI), wording such as
  “Click **X** in the top-left corner” is preferred over “Click **X** on the
  left-hand side”.
- The instructions should assume that the user is already logged onto the
  third-party service in question, so instructions such as “Log on to your
  account” are generally redundant.
- If there are 4 sentences, the middle two sentences should generally be joined
  with an "and". As an example,"Click W. Click X, and click Y. Click Z” flows
  better than "Click W. Click X. Click Y. Click Z.".
- Avoid multiple paragraphs in a single step. If the setup process is too
  complicated, it might make sense to split it into multiple steps. In that
  case, a single step constitutes the instructions the user needs to carry out
  on a single screen on the third-party’s website.
- When instructing the users to navigate to a specific part of the third-party
  UI, the instructions should explicitly mention the service’s name. For
  example, “Go to your repository’s settings on GitHub”, and not just “Go to
  your repository’s settings” to make sure that there is no confusion about
  which service a step belongs to.
