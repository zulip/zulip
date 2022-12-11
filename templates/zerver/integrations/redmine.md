Get information on new or updated Redmine issues right in
Zulip with our Zulip Redmine plugin!

_Note: this setup must be done by a Redmine Administrator._

### Installing

Following the [Redmine plugin installation guide][1]:

1. Start by changing to the Redmine instance root directory:
  `cd /path/to/redmine/instance`

1. Clone the [Zulip Redmine plugin repository][2] into the `plugins` subdirectory
   of your Redmine instance.
   `git clone https://github.com/zulip/zulip-redmine-plugin plugins/redmine_zulip`

1. Update the Redmine database by running (for Rake 2.X, see
   the guide for instructions for older versions):
   `rake redmine:plugins:migrate RAILS_ENV=production`

1. Restart your Redmine instance.

The Zulip plugin is now registered with Redmine!

### Global settings

1. {!create-an-incoming-webhook.md!}

2. Log in to your Redmine instance, click on **Administration** in the top-left
corner, then click on **Plugins**.

3. Find the **Redmine Zulip** plugin, and click **Configure**. Fill
out the following fields:

    * Zulip URL (e.g `https://yourZulipDomain.zulipchat.com/`)
    * Zulip Bot E-mail
    * Zulip Bot API key
    * Stream name __*__
    * Issue updates subject __*__
    * Version updates subject __*__

    _* You can use the following variables in these fields:_

    * ${issue_id}
    * ${issue_subject}
    * ${project_name}
    * ${version_name}

### Project settings

To override the global settings for a specific project, go to the
project's **Settings** page, and select the **Zulip** tab.

{!congrats.md!}

![Redmine bot message](/static/images/integrations/redmine/001.png)

[1]: https://www.redmine.org/projects/redmine/wiki/Plugins
[2]: https://github.com/zulip/zulip-redmine-plugin
