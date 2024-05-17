# Import from Rocket.Chat

You can import your current workspace into a Zulip organization. It's a great
way to preserve your workspace history when you migrate to Zulip, and to make
the transition easy for the members of your organization.

The import will include your organization's:

* **Name**
* **Message history**, including attachments and emoji reactions
* **Users**, including names, emails, roles, and teams
* **Channels**, including discussions and all user subscriptions
* **Custom emoji**

## Import process overview

To import your Rocket.Chat organization into Zulip, you will need to take the
following steps, which are described in more detail below:

{start_tabs}

1. [Export your Rocket.Chat data](#export-your-rocketchat-data).

1. [Import your Rocket.Chat data into Zulip](#import-your-data-into-zulip).

1. [Get your organization started with Zulip](#get-your-organization-started-with-zulip)!

{end_tabs}

## Import your organization from Rocket.Chat into Zulip

### Export your Rocket.Chat data

Rocket.Chat does not provide an official data export feature, so the Zulip
import tool works by importing data from a Rocket.Chat database dump.

If you're self-hosting your Rocket.Chat instance, you can create a
database dump using the `mongodump` utility.

If your organization is hosted on Rocket.Chat Cloud or another hosting
provider that doesn't provide you with database access, you will need
to request a database dump by contacting their
[support](https://docs.rocket.chat/resources/frequently-asked-questions/cloud-faqs#data-export).

In either case, you should end up with a directory containing many
`.bson` files.

### Import your data into Zulip

{!import-your-data-into-zulip.md!}

At this point, you should go to the directory containing all the `.bson` files
from your database dump and rename it to `rocketchat_data`. This directory will
be your **exported data** file in the instructions below.

{start_tabs}

{tab|zulip-cloud}

{!import-into-a-zulip-cloud-organization.md!}

{!import-zulip-cloud-organization-warning.md!}

{tab|self-hosting}

{!import-into-a-self-hosted-zulip-server.md!}

1. To import into an organization hosted on the root domain
   (`EXTERNAL_HOST`) of the Zulip installation, run the following
   commands.

    {!import-self-hosted-server-tips.md!}

    ```
    cd /home/zulip/deployments/current
    ./scripts/stop-server
    ./manage.py convert_rocketchat_data /tmp/rocketchat_data --output /tmp/converted_rocketchat_data
    ./manage.py import '' /tmp/converted_rocketchat_data
    ./scripts/start-server
    ```

    Alternatively, to import into a custom subdomain, run:

    ```
    cd /home/zulip/deployments/current
    ./scripts/stop-server
    ./manage.py convert_rocketchat_data /tmp/rocketchat_data --output /tmp/converted_rocketchat_data
    ./manage.py import <subdomain> /tmp/converted_rocketchat_data
    ./scripts/start-server
    ```

1. Follow [step 4](https://zulip.readthedocs.io/en/stable/production/install.html#step-4-configure-and-use)
   of the guide for [installing a new Zulip
   server](https://zulip.readthedocs.io/en/stable/production/install.html).

{end_tabs}

#### Import details

Whether you are using Zulip Cloud or self-hosting Zulip, here are a few notes to
keep in mind about the import process:

- Rocket.Chat does not export workspace settings, so you will need to [configure
  the settings for your Zulip organization](/help/customize-organization-settings).
  This includes settings like [email
  visibility](/help/configure-email-visibility),
  [message editing permissions](/help/restrict-message-editing-and-deletion),
  and [how users can join your organization](/help/restrict-account-creation).

- Rocket.Chat does not export user settings, so users in your organization may
  want to [customize their account settings](/help/getting-started-with-zulip).

- Rocket.Chat user roles are mapped to Zulip's [user
  roles](/help/roles-and-permissions) in the following way:

| Rocket.Chat role | Zulip role |
|------------------|------------|
| Admin            | Owner      |
| User             | Member     |
| Guest            | Guest      |

- User avatars are not imported.

- Default channels for new users are not imported.

- Starred messages are not imported.

- Messages longer than Zulip's limit of 10,000 characters are not
  imported.

- Messages from Rocket.Chat Discussions are imported as topics
  inside the Zulip channel corresponding to the parent channel of the
  Rocket.Chat Discussion.

- Messages from Rocket.Chat Discussions having direct channels
  (i.e. direct messages) as their parent are imported as normal
  direct messages in Zulip.

- While Rocket.Chat Threads are in general imported as separate
  topics, Rocket.Chat Threads within Rocket.Chat Discussions are
  imported as normal messages within the topic containing that
  Discussion, and Threads in Direct Messages are imported as normal
  Zulip direct messages.

Additionally, because Rocket.Chat does not provide a documented or
stable data export API, the import tool may require small changes from
time to time to account for changes in the Rocket.Chat database
format.  Please [contact us](/help/contact-support) if you encounter
any problems using this tool.

## Get your organization started with Zulip

{!import-get-your-organization-started.md!}

## Decide how users will log in

{!import-how-users-will-log-in.md!}

## Related articles

* [Choosing between Zulip Cloud and self-hosting](/help/zulip-cloud-or-self-hosting)
* [Setting up your organization](/help/getting-your-organization-started-with-zulip)
* [Getting started with Zulip](/help/getting-started-with-zulip)
