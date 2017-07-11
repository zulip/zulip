# Add a bot or integration

Bots and integrations are features that are accessible to all members of an organization.

## Add a bot

{!go-to-the.md!} [Your bots](/#settings/your-bots)
{!settings.md!}

2. On this page, under the **Add a new bot** view, enter the bot type,
   a name, an email, and optionally an avatar for your bot.
   Then click the **Create bot** button to create your bot.

    ![Bots page](/static/images/help/add_a_new_bot.png)

3. An entry such as the following should appear above the **Add a new bot** view, confirming
the creation of your bot.

    ![Example bot](/static/images/help/bot_example.png)

4. You now have access to your bot's API key and API
configuration file (`.zuliprc`) which you will need for integrations that you would like
to use with this bot. You can click on the download
(<i class="icon-vector-download-alt"></i>) icon to download your `.zuliprc` file.

### Bot types

You can create three types of bots:

![Bot types](/static/images/help/bot_types.png)

* **Generic bot:** A generic bot can send *and* receive messages.

* **Incoming webhook:**  The API keys for such bots are limited to
  only sending messages and can't receive messages. Thus, this bot
  type lessens the security risks associated with exposing such API
  keys to third-party services, since they can't be used to read
  messages.

* **Outgoing webhook:** Bots of this type are the same as a
  **Generic bot**, except **Outgoing webhooks** bots have an extra field
  for the base URL of the third-party service being requested.
  **Outgoing webhook** bots send POST requests to this base URL.

## Add an integration

The [Integrations page](/integrations) offers a complete list of all the
integrations currently supported by Zulip. To add an integration to your
organization, select the integration that you would like to use from the list
and follow the installation instructions accordingly.
