# Import from Rocket.Chat

Starting with Zulip 5.0, Zulip supports importing data from Rocket.Chat,
including users, teams, channels, discussions, messages, and more.

**Note:** You can only import a Rocket.Chat workspace as a new Zulip
organization. In particular, you cannot use this tool to import data
into an existing Zulip organization.

## Import from Rocket.Chat

First, you need to export your data from Rocket.Chat. Rocket.Chat does
not provide an official data export feature, so the Zulip import tool
works by importing data from a Rocket.Chat database dump.

If you're self-hosting your Rocket.Chat instance, you can create a
database dump using the `mongodump` utility.

If your organization is hosted on Rocket.Chat Cloud or another hosting
provider that doesn't provide you with database access, you will need
to request a database dump by contacting their support.

In either case, you should end up with a directory containing many
`.bson` files.

### Import into Zulip Cloud

Email support@zulip.com with your database dump and your desired
Zulip subdomain. Your imported organization will be hosted at
`<subdomain>.zulipchat.com`.

If you've already created a test organization at
`<subdomain>.zulipchat.com`, let us know, and we can rename the old
organization first.

### Import into a self-hosted Zulip server

First [install a new Zulip
server](https://zulip.readthedocs.io/en/stable/production/install.html)
with Zulip 5.0 or newer, skipping "Step 3: Create a Zulip
organization, and log in" (you'll create your Zulip organization via
the data import tool instead).

Now, get the directory containing all the `bson` files in your database
dump and save it inside `/home/zulip/rocketchat` on your Zulip server and rename it
to `rocketchat` (the directory at `/home/zulip/rocketchat` should contain
all the `bson` files).

Log in to a shell on your Zulip server as the `zulip` user. To import with
the most common configuration, run the following commands:

```
cd /home/zulip/deployments/current
./scripts/stop-server
./manage.py convert_rocketchat_data /home/zulip/rocketchat --output /home/zulip/converted_rocketchat_data
./manage.py import "" /home/zulip/converted_rocketchat_data
./scripts/start-server
```

This could take a few seconds to several minutes to run, depending on how
much data you're importing. The server stop/restart is only necessary
when importing on a server with minimal RAM, where an OOM kill might
otherwise occur.

**Import options**

The commands above create an imported organization on the root domain
(`EXTERNAL_HOST`) of the Zulip installation. You can also import into a
custom subdomain, e.g. if you already have an existing organization on the
root domain. Replace the last line above with the following, after replacing
`<subdomain>` with the desired subdomain.

```
./manage.py import <subdomain> /home/zulip/converted_rocketchat_data
```

{!import-login.md!}

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/upgrade-or-modify.html#upgrading-from-a-git-repository

## Caveats

This import tool is currently beta has the following known limitations:

-   User avatars are not imported.
-   Default channels for new users are not imported.
-   Messages longer than Zulip's limit of 10,000 characters are not
    imported.
-   Livechat channels/messages are not imported.
-   Messages from Rocket.Chat Discussions are imported as topics
    inside the Zulip stream corresponding to the parent channel of the
    Rocket.Chat Discussion.
-   Messages from Rocket.Chat Discussions having direct channels
    (i.e. private messages) as their parent are imported as normal
    private messages in Zulip.
-   If a user is subscribed to a Rocket.Chat Discussion but not to
    its parent channel, they will lose access to that Discussion
    (now topic) upon migration to Zulip and will need to be explicitly
    subscribed to the whole parent stream to gain back the access.
    Starred messages from such discussions are also not imported.
-   While Rocket.Chat Threads are in general imported as separate
    topics, Rocket.Chat Threads within Rocket.Chat Discussions are
    imported as normal messages within the topic containing that
    Discussion, and Threads in Direct Messages are imported as normal
    Zulip private messages.

Additionally, because Rocket.Chat does not provide a documented or
stable data export API, the import tool may require small changes from
time to time to account for changes in the Rocket.Chat database
format.  Please [contact us](/help/contact-support) if you encounter
any problems using this tool.

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/upgrade-or-modify.html#upgrading-from-a-git-repository
