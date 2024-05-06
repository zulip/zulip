# Documenting an integration

In order for a [Zulip
integration](https://zulip.com/api/integrations-overview) to be useful
to users, it must be documented. Zulip's common system for documenting
integrations involves writing Markdown files, either at
`zerver/webhooks/{webhook_name}/doc.md` (for webhook integrations) or
`templates/zerver/integrations/{integration_name}.md` (for other
integrations).

Usually, this involves a few steps:

- Add text explaining all of the steps required to set up the
  integration, including what URLs to use, etc. See
  [Writing guidelines](#writing-guidelines) for detailed writing guidelines.

  Zulip's pre-defined Markdown macros can be used for some of these steps.
  See [Markdown macros](#markdown-macros) for further details.

- Make sure you've added your integration to
  `zerver/lib/integrations.py` in both the `WEBHOOK_INTEGRATIONS`
  section (or `INTEGRATIONS` if not a webhook), and the
  `DOC_SCREENSHOT_CONFIG` sections. These registries configure your
  integration to appear on the `/integrations` page and make it
  possible to automatically generate the screenshot of a sample
  message (which is important for the screenshots to be updated as
  Zulip's design changes).

- You'll need to add an SVG graphic
  of your integration's logo under the
  `static/images/integrations/logos/<name>.svg`, where `<name>` is the
  name of the integration, all in lower case; you can usually find them in the
  product branding or press page. Make sure to optimize the SVG graphic by
  running `tools/setup/optimize-svg`. This will also run
  `tools/setup/generate_integration_bots_avatars.py` automatically to generate
  a smaller version of the image you just added and optimized. This smaller image will be
  used as the bot avatar in the documentation screenshot that will be generated
  in the next step.

  If you cannot find an SVG graphic of the logo, please find and include a PNG
  image of the logo instead.

- Finally, generate a message sent by the integration and take a screenshot of
  the message to provide an example message in the documentation.

  If your new integration is an incoming webhook integration, you can generate
  the screenshot using `tools/generate-integration-docs-screenshot`:

  ```bash
  ./tools/generate-integration-docs-screenshot --integration integrationname
  ```

  If you have trouble using this tool, you can also manually generate the
  screenshot using `manage.py send_webhook_fixture_message`. When generating the
  screenshot of a sample message using this method, give your test bot a nice
  name like "GitHub Bot", use the project's logo as the bot's avatar, and take
  the screenshot showing the channel/topic bar for the message, not just the
  message body.

## Markdown macros

**Macros** are elements in the format of `{!macro.md!}` that insert common
phrases and steps at the location of the macros. Macros help eliminate
repeated content in our documentation.

The source for macros is the Markdown files under
`templates/zerver/integrations/include/` in the
[main Zulip server repository](https://github.com/zulip/zulip). If you find
multiple instances of particular content in the documentation, you can
always create a new macro by adding a new file to that folder.

Here are a few common macros used to document Zulip's integrations:

- `{!create-channel.md!}` macro - Recommends that users create a dedicated
  channel for a given integration. Usually the first step is setting up an
  integration or incoming webhook. For an example rendering, see **Step 1** of
  [the docs for Zulip's GitHub integration][github-integration].

- `{!create-an-incoming-webhook.md!}` macro - Instructs users to create a bot
  for a given integration and select **Incoming webhook** as the **Bot type**.
  This macro is usually used right after `{!create-channel.md!}`. For an example
  rendering, see **Step 2** of [the docs for Zulip's Zendesk integration][zendesk].

- `{!create-a-generic-bot.md!}` macro - Instructs users to create a bot
  for a given integration and select **Generic bot** as the **Bot type**. For an
  example rendering, see [the docs for Zulip's Matrix integration][matrix].

- `{!create-an-incoming-webhook.md!}` macro - Instructs users to create a bot
  for a given integration and select **Incoming webhook** as the **Bot type**.
  This macro is usually used right after `{!create-channel.md!}`. For an example
  rendering, see **Step 2** of [the docs for Zulip's GitHub integration][github-integration].

  **Note:** If special configuration is
  required to set up the URL and you can't use this macro, be sure to use the
  `{{ api_url }}` template variable, so that your integration
  documentation will provide the correct URL for whatever server it is
  deployed on. If special configuration is required to set the `SITE`
  variable, you should document that too.

- `{!generate-integration-url.md!}` - Instructs user how to get the URL for a
  bot for a given integration. An example URL is generated automatically for
  every incoming webhook by using attributes in the `WebhookIntegration` class
  in [zerver/lib/integrations.py][integrations-file].

- `{!append-channel-name.md!}` macro - Recommends appending `&stream=channel_name`
  to a URL in cases where supplying a channel name in the URL is optional.
  Supplying a channel name is optional for most Zulip integrations. If you use
  `{!generate-integration-url.md!}`, this macro need not be used.

- `{!append-topic.md!}` macro - Recommends appending `&topic=my_topic` to a URL
  to supply a custom topic for webhook notification messages. Supplying a custom
  topic is optional for most Zulip integrations. If you use
  `{!generate-integration-url.md!}`, this macro need not be used.

- `{!congrats.md!}` macro - Inserts congratulatory lines signifying the
  successful setup of a given integration. This macro is usually used at
  the end of the documentation, right before the sample message screenshot.
  For an example rendering, see the end of
  [the docs for Zulip's GitHub integration][github-integration].

- `{!download-python-bindings.md!}` macro - Links to Zulip's
  [API page](https://zulip.com/api/) to download and install Zulip's
  API bindings. This macro is usually used in non-webhook integration docs under
  `templates/zerver/integrations/<integration_name>.md`. For an example
  rendering, see **Step 3** of
  [the docs for Zulip's Codebase integration][codebase].

- `{!change-zulip-config-file.md!}` macro - Instructs users to create a bot and
  specify said bot's credentials in the config file for a given non-webhook
  integration. This macro is usually used in non-webhook integration docs under
  `templates/zerver/integrations/<integration_name>.md`. For an example
  rendering, see **Step 4** of
  [the docs for Zulip's Codebase integration][codebase].

- `{!git-append-branches.md!}` and `{!git-webhook-url-with-branches.md!}` -
  These two macros explain how to specify a list of branches in the webhook URL
  to filter notifications in our Git-related webhooks. For an example rendering,
  see the last paragraph of **Step 2** in
  [the docs for Zulip's GitHub integration][github-integration].

- `{!webhook-url.md!}` - Used internally by `{!generate-integration-url.md!}`
  to generate the webhook URL.

- `{!webhook-url-with-bot-email.md!}` - Used in certain non-webhook integrations
  to generate URLs of the form:

  ```text
  https://bot_email:bot_api_key@yourZulipDomain.zulipchat.com/api/v1/external/beanstalk
  ```

  For an example rendering, see
  [Zulip's Beanstalk integration](https://zulip.com/integrations/doc/beanstalk).

- `{!event-filtering-instructions}` macro - Instructs user to use the event
  filtering feature and shows a list of event types that the integration supports.
  For an example rendering, see the last 4 paragraphs of **Step 2** in
  [the docs for Zulip's Front integration][front].

[github-integration]: https://zulip.com/integrations/doc/github
[zendesk]: https://zulip.com/integrations/doc/zendesk
[matrix]: https://zulip.com/integrations/doc/matrix#configure-the-bridge
[codebase]: https://zulip.com/integrations/doc/codebase
[beanstalk]: https://zulip.com/integrations/doc/beanstalk
[front]: https://zulip.com/integrations/doc/front
[integrations-file]: https://github.com/zulip/zulip/blob/main/zerver/lib/integrations.py

## Writing guidelines

For the vast majority of integrations, you should just copy the docs for a
similar integration and edit it. [Basecamp][basecamp] is a good one to copy.

[basecamp]: https://zulip.com/integrations/doc/basecamp

### General writing guidelines

At a high level, the goals are for the instructions to feel simple, be easy to
follow, and be easy to maintain. Easier said than done, but here are a few
concrete guidelines.

##### Feel simple

- Use simple language.
- Use the imperative tense.
- Only describe things as much as necessary. For example: "Select **Project settings**."
  is better than "Select **Project settings** from the dropdown."
- Cut unnecessary words. For example, do not start steps with transition words
  like "Next", "First", "Now", etc. Each step should be structurally
  independent.

##### Be easy to follow

- Actions should appear in order, including implicit ones. So "Under
  **Webhooks**, click **Add Webhook**." not "Click **Add Webhook** in the
  **Webhooks** section." "Under **Webhooks**" is an action, since it’s basically
  the same as "Find the Webhooks section".
- UI elements in third-party websites should be **bolded**.
- Trailing punctuation can be stripped from bolded elements. For example,
  "**Enable this checkbox**" instead of "**Enable this checkbox?**".
  Starting punctuation such as the "**+**" in "**+ New Notification**" should
  be preserved.
- You can use a screenshot if a step is particularly complicated
  (see [Screenshots](#screenshots) below).

##### Be easy to maintain

- Follow the organization and wording of existing docs as much as possible.

### Guidelines for specific steps

Most doc files should start with a generic sentence about the
integration, for example, "Get `webhook name` notifications in Zulip!"
A typical doc will then have the following steps.

##### "Create the channel" step

- Use the `create-channel` macro. This step should be omitted if the
  integration only supports notifications via direct messages.

##### "Create the bot" step

- Typically, use the `create-an-incoming-webhook` and
  `generate-integration-url` macros.
- [Existing macros](#markdown-macros) should be used for this if they exist,
  but if the macro defaults don’t work, it may make sense to write something
  custom for the integration in question. This step is mandatory for all
  integrations.

##### "Navigate to this screen" step

- In general, this should be one step, even if it takes multiple clicks.
- Begin by mentioning the third-party service being documented with language
  such as "Go to your Taiga project", "Go to your GitHub repository",
  "On your X project", etc. Assume the user is already logged in to their
  account.
- If a UI element is difficult to spot, you can use additional cues like
  "Click on **Settings** in the top-right corner" or "On the left, click
  **Webhooks**.". Only do this if the element is actually difficult to spot.
- If this step includes more than 5 sentences, it may need to be split up
  into multiple steps.

##### "Fill out form and save" step

- Filling out a form and clicking **Save** should generally be one step, even if
  there are multiple fields to fill out.
- It’s fine to say things like "Follow the on-screen instructions to create an
  app" if they have a sequence of steps they guide you through that are pretty
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
- Each screenshot should come after the step that refers to it.
