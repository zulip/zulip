# Documenting an integration

In order for a [Zulip
integration](https://zulip.com/api/integrations-overview) to be useful
to users, it must be documented. Zulip's common system for documenting
integrations involves writing Markdown files, either at
`zerver/webhooks/{webhook_name}/doc.md` (for webhook integrations) or
`templates/zerver/integrations/{integration_name}.md` (for other
integrations).

The [integrations][api-integrations] in
[zulip/python-zulip-api][api-repo] have their corresponding Markdown files
at `zulip/integrations/{integration_name}/doc.md`, which are imported into
[zulip/zulip][zulip-repo] at
`static/generated/integrations/{integration_name}/doc.md` using the
`tools/setup/generate_bots_integrations_static_files.py` script.

[api-repo]: https://github.com/zulip/python-zulip-api/
[api-integrations]: https://github.com/zulip/python-zulip-api/tree/main/zulip/integrations
[zulip-repo]: https://github.com/zulip/zulip

Typically, the documentation process involves the following steps:

- Add text explaining all of the steps required to set up the
  integration, including what URLs to use, etc. See
  [Writing guidelines](#writing-guidelines) for detailed writing guidelines.

  Zulip's pre-defined Markdown macros can be used for some of these steps.
  See [Markdown macros](#markdown-macros) for further details.

- Make sure you've added your integration to `zerver/lib/integrations.py` in
  both the `WEBHOOK_INTEGRATIONS` section (or `INTEGRATIONS` if not a
  webhook), and the `DOC_SCREENSHOT_CONFIG` sections.

  These registries configure your integration to appear on the
  `/integrations` page, and make it possible to automatically generate the
  screenshot of an example message, which is important for the screenshots
  to be updated as Zulip's design changes.

- You'll need to add an SVG graphic of your integration's logo under the
  `static/images/integrations/logos/<name>.svg`, where `<name>` is the
  name of the integration, all in lower case; you can usually find them in the
  product branding or press page. Make sure to optimize the SVG graphic by
  running `tools/setup/optimize-svg`. This will also run
  `tools/setup/generate_integration_bots_avatars.py` automatically to generate
  a smaller version of the image you just added and optimized. This smaller
  image will be used as the bot avatar in the documentation screenshot that
  will be generated in the next step.

  If you cannot find an SVG graphic of the logo, please find and include a PNG
  image of the logo instead.

- Finally, you will need to generate a message sent by the integration, and
  generate a screenshot of the message to provide an example message in the
  integration's documentation.

  If your new integration is not a webhook and does not have fixtures, add a
  message template and topic to `zerver/webhooks/fixtureless_integrations.py`.
  Then, add your integration's name to `FIXTURELESS_INTEGRATIONS_WITH_SCREENSHOTS`
  in `zerver/lib/integrations.py`.

  Otherwise, you should have already added your integration to
  `WEBHOOK_SCREENSHOT_CONFIG`.

  Generate the screenshot using `tools/screenshots/generate-integration-docs-screenshot`,
  where `integrationname` is the name of the integration:

  ```bash
  ./tools/screenshots/generate-integration-docs-screenshot --integration integrationname
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
  [the docs for Zulip's Zendesk integration][zendesk].

- `{!create-an-incoming-webhook.md!}` macro - Instructs users to create a bot
  for a given integration and select **Incoming webhook** as the **Bot type**.
  This macro is usually used right after `{!create-channel.md!}`. For an example
  rendering, see **Step 2** of [the docs for Zulip's Zendesk integration][zendesk].

- `{!create-a-generic-bot.md!}` macro - Instructs users to create a bot
  for a given integration and select **Generic bot** as the **Bot type**. For an
  example rendering, see [the docs for Zulip's Matrix integration][matrix].

- `{!generate-webhook-url-basic.md!}` - Instructs user how to get the URL for a
  bot for a given integration. Note that this macro should not be used with the
  `{!create-channel.md!}` macro. For an example rendering, see **Step 2** of
  [the docs for Zulip's GitHub integration][github-integration].

- `{!generate-integration-url.md!}` - Instructs user how to get the URL for a
  bot for a given integration. An example URL is generated automatically for
  every incoming webhook by using attributes in the `WebhookIntegration` class
  in [zerver/lib/integrations.py][integrations-file].

  **Note:** If special configuration is required to set up the URL and you can't
  use these macros, be sure to use the `{{ api_url }}` template variable, so
  that your integration documentation will provide the correct URL for whatever
  server it is deployed on.

- `{!congrats.md!}` macro - Inserts congratulatory lines signifying the
  successful setup of a given integration. This macro is usually used at
  the end of the documentation, right before the sample message screenshot.
  For an example rendering, see the end of
  [the docs for Zulip's GitHub integration][github-integration].

- `{!event-filtering-additional-feature.md!}` macro - If a webhook integration
  supports event filtering, then this adds a section with the specific
  events that can be filtered for the integration. Should be included in
  the documentation if `all_event_types` is set in the webhook integration
  view. For an example see, the **Filtering incoming events** section in
  [Zulip's GitLab integration][gitlab].

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

- `{!webhook-url-with-bot-email.md!}` - Used in certain non-webhook integrations
  to generate URLs of the form:

  ```text
  https://bot_email:bot_api_key@your-org.zulipchat.com/api/v1/external/beanstalk
  ```

  For an example rendering, see
  [Zulip's Beanstalk integration](https://zulip.com/integrations/doc/beanstalk).

[github-integration]: https://zulip.com/integrations/doc/github
[zendesk]: https://zulip.com/integrations/doc/zendesk
[matrix]: https://zulip.com/integrations/doc/matrix#configure-the-bridge
[codebase]: https://zulip.com/integrations/doc/codebase
[beanstalk]: https://zulip.com/integrations/doc/beanstalk
[front]: https://zulip.com/integrations/doc/front
[gitlab]: https://zulip.com/integrations/doc/gitlab
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

## Markdown features

Zulip's Markdown processor allows you to include several special features in
your documentation to help improve its readability:

- Since raw HTML is supported in Markdown, you can include arbitrary
  HTML/CSS in your documentation as needed.

- Code blocks allow you to highlight syntax, similar to
  [Zulip's own Markdown](https://zulip.com/help/format-your-message-using-markdown).

- Anchor tags can be used to link to headers in other documents.

- Inline [icons](#icons) are used to refer to features in the Zulip UI.

- Utilize [macros](#markdown-macros) to limit repeated content in the documentation.

- Create special highlight warning blocks using
  [tips and warnings](#tips-and-warnings).

- Format instructions with tabs using
  [Markdown tab switcher](#tab-switcher).

### Icons

See [icons documentation](../subsystems/icons.md). Icons should always be
referred to with their in-app tooltip or a brief action name, _not_ the
name of the icon in the code.

### Tips and warnings

A **tip** is any suggestion for the user that is not part of the main set of
instructions. For instance, it may address a common problem users may
encounter while following the instructions, or point to an option for power
users.

```md
!!! tip ""

    If you want notifications for issues, as well as events, you can
    scroll down to **Webhooks** on the same page, and toggle the
    **issue** checkbox.
```

A **keyboard tip** is a note for users to let them know that the same action
can also be accomplished via a [keyboard shortcut](https://zulip.com/help/keyboard-shortcuts).

```md
!!! keyboard_tip ""

    Use <kbd>D</kbd> to bring up your list of drafts.
```

A **warning** is a note on what happens when there is some kind of problem.
Tips are more common than warnings.

```md
!!! warn ""

    **Note**: Zulip also supports configuring this integration as a
    webhook in Sentry.
```

All tips/warnings should appear inside tip/warning blocks. There
should be only one tip/warning inside each block, and they usually
should be formatted as a continuation of a numbered step.

### Tab switcher

Our Markdown processor supports easily creating a tab switcher widget
design to easily show the instructions for different languages in API
docs, etc. To create a tab switcher, write:

```md
{start_tabs}
{tab|python}
# First tab's content
{tab|js}
# Second tab's content
{tab|curl}
# Third tab's content
{end_tabs}
```

The tab identifiers (e.g., `python` above) and their mappings to
the tabs' labels are declared in
[zerver/lib/markdown/tabbed_sections.py][tabbed-sections-code].

This widget can also be used just to create a nice box around a set of
instructions
([example](https://zulip.com/help/deactivate-your-account)) by
only declaring a single tab, which is often used for the main set of
instructions for setting up an integration.

[tabbed-sections-code]: https://github.com/zulip/zulip/blob/main/zerver/lib/markdown/tabbed_sections.py
