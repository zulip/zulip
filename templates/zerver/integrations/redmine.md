Get information on new or updated Redmine issues right in
Zulip with our Zulip Redmine plugin! Note: this setup must be
done by a Redmine Administrator.

{!create-stream.md!}

Clone the [Zulip Redmine plugin repository][1] by running:
`git clone https://github.com/zulip/zulip-redmine-plugin`

[1]: https://github.com/zulip/zulip-redmine-plugin

Follow the [Redmine plugin installation guide][2] to install
the `zulip_redmine` plugin directory, which is a subdirectory
of the `zulip-redmine-plugin` repository directory. In a nutshell,
the steps are:

1. Copy the `zulip_redmine` directory to the `plugins`
   directory of your Redmine instance.

2. Update the Redmine database by running (for Rake 2.X, see
   the guide for instructions for older versions):
   `rake redmine:plugins:migrate RAILS_ENV=production`

3. Restart your Redmine instance.

The Zulip plugin is now registered with Redmine!

[2]: http://www.redmine.org/projects/redmine/wiki/Plugins

On your {{ settings_html|safe }}, create a new Redmine bot.

To configure Zulip notification settings that apply to many
projects in one go, in Redmine click the **Administration** link in
the top left. Click the **Plugins** link on the Administration page,
and click the **Configure** link to the right of the Zulip plugin
description. In the **Projects** section, select all projects to which
you want these settings to apply.

To configure Zulip notifications for a particular Redmine project,
visit the project's **Settings** page.

In either case, fill out the settings with the Zulip server
(`{{ api_url_scheme_relative }}`), the bot's email address and API key,
and the Zulip stream that should receive notifications, and apply your
changes.

To test the plugin, create an issue or update an existing issue
in a Redmine project that has Zulip notifications configured (any
project, if you've configured global settings).

{!congrats.md!}

![](/static/images/integrations/redmine/001.png)
