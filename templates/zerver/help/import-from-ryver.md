# Import from Ryver (beta)

Zulip supports importing data from Ryver, including users, forums,
teams, topics in forums/teams, non-private messages, and local server attachments.

Features that are possible but may come in the future - avatars, emojis,
tasks, 

**Note:** You can only import Ryver as a new Zulip organization. In
particular, this tool you cannot use this tool to import from Ryver into an
existing Zulip organization.

## Before you begin

This import tool mainly utilizes Ryver API calls. As such there are several limitations.

1. The account used to extract needs to be a member of every Forum and Team you wish to extract. 
We recommend you ask Ryver support for a full list of Forums/Teams as Ryver Admins cannot see them all.
To get your data the account email/password or base64 must be used for use with the API. We recommend
creating a new account specifically for the export purpose. You may need to coordinate with your organization
in order to add the special account to every Forum/Team.
2. It is possible your network configurations will make some tasks such as attachment downloads impossible. 
Please try to keep parity as if you were a normal user.

## Extracting the data into Zulip friendly format

This step can be done yourself or with assistance from the Zulip support team. If you choose the 
later you will need to share the exporting account details for API access.

Log in to a shell on your Zulip server as the `zulip` user. To import with
the most common configuration, run the following commands.

```
cd /home/zulip/deployments/current
./manage.py convert_ryver_data --api-endpoint=https://example.ryver.com/api/1/odata.svc --account-user=yourexportuser@yourorganization.com --output converted_ryver_data

```

This will take several minutes to hours long, depending on how much data you're
importing.

### Import data into zulipchat.com

The output from extraction will include the --output directory as a .tar.gz file.
Simply email that file to support@zulipchat.com with it attached and your desired subdomain.
Your imported organization will be hosted at `<subdomain>.zulipchat.com`.

If you've already created a test organization at
`<subdomain>.zulipchat.com`, let us know, and we can rename the old
organization first.

### Import data into self-hosted Zulip server

First
[install a new Zulip server](https://zulip.readthedocs.io/en/stable/production/install.html),
skipping "Step 3: Create a Zulip organization, and log in" (you'll
create your Zulip organization via the data import tool instead).

After the instructions in extracting simply run the final command
```
./manage.py import '' converted_ryver_data
```

**Import options**

The command above create an imported organization on the root domain
(`EXTERNAL_HOST`) of the Zulip installation. You can also import into a
custom subdomain, e.g. if you already have an existing organization on the
root domain. Replace the last line above with the following, after replacing
`<subdomain>` with the desired subdomain.

```
./manage.py import <subdomain> converted_ryver_data
```

{!import-login.md!}

## Create organization administrators

This is currently not implemented in the export script but is possible and likely 
to become a feature soon. You can follow the Zulip documentation on
[making a user an administrator from the terminal][grant-admin-access]
to mark the appropriate users as administrators.

[grant-admin-access]: https://zulip.readthedocs.io/en/latest/production/management-commands.html#grant-administrator-access)

## Additional Caveats

- This tool does not, nor will ever, support Private Messages exports

- This tool doesn't translate Ryver's markdown format into Zulip markdown.
