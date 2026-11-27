# Zulip services

Zulip's maintainers operate the following services for self-hosted
Zulip servers:

- The [Mobile Push Notification Service](mobile-push-notifications.md)
  forwards mobile push notifications to the Zulip mobile apps.

To use these services, register your server and enable the services
you need in `/etc/zulip/settings.py`. Your server uses the same
registration for all services. See each service's documentation for
its requirements and setup instructions.

## Registering your server

:::{important}

If you used the `--push-notifications` option when
[installing Zulip](install.md#step-2-install-zulip) 10.0 or newer,
your server is already registered.

These instructions apply to Zulip 9.0+. If you are running an older
version of Zulip ([check](https://zulip.com/help/view-zulip-version)
if you are unsure), see the [Zulip 8.x
documentation](https://zulip.readthedocs.io/en/8.4/production/mobile-push-notifications.html).
:::

1. Make sure your server has outgoing HTTPS access to the public Internet. If
   that is restricted by a proxy, you will need to [configure Zulip to use your
   outgoing HTTP proxy](deployment.md#customizing-the-outgoing-http-proxy)
   first.

1. Make sure that the `ZULIP_ADMINISTRATOR` setting in your
   `/etc/zulip/settings.py` file is a real email address which you
   monitor. If Zulip's maintainers need to contact you regarding your
   server, they will use this email address. [See
   below](#updating-your-servers-registration) for instructions if
   this contact needs to be updated later.

1. Enable the services you want to use by uncommenting the appropriate
   lines [in settings.py][update-settings-docs]. For example, setting
   `ZULIP_SERVICE_PUSH_NOTIFICATIONS = True` enables the [Mobile Push
   Notification Service](mobile-push-notifications.md).

1. Decide whether to share usage statistics with the Zulip team.

   By default, Zulip installations using the Mobile Push Notification Service
   submit additional usage statistics that help Zulip's maintainers allocate
   resources towards supporting self-hosted installations
   ([details](#uploading-usage-statistics)). You can disable submitting usage
   statistics now or at any time by setting
   `ZULIP_SERVICE_SUBMIT_USAGE_STATISTICS=False` in `/etc/zulip/settings.py`
   (uncomment the appropriate line).

   Note that all systems using Zulip services upload the [basic
   metadata](#uploading-basic-metadata) required for the services they use.

   [update-settings-docs]: ../production/upgrade.md#updating-settingspy-inline-documentation

1. [Restart your Zulip server](settings.md#changing-server-settings) so that
   your configuration changes take effect.

1. Run the registration command. If you installed Zulip directly on the server
   (without Docker), run as root:

   ```
   su zulip -c '/home/zulip/deployments/current/manage.py register_server'
   ```

   Or if you're {doc}`using Docker <docker:index>`, run:

   ```
   cd docker-zulip
   ./manage.py register_server
   ```

   This command will print the registration data it would send, ask you to
   accept the terms of service, and if you accept, register your server. If
   you have trouble, [contact Zulip
   support](https://zulip.com/help/contact-support) with the output of this
   command.

## What your server uploads

The metadata your server uploads depends on which services you enable.
Uploading usage statistics is optional.

### Uploading basic metadata

All Zulip installations running Zulip 8.0 or greater that use Zulip
services regularly upload basic metadata about the organizations hosted
by the installation. (Older Zulip servers upload these metadata only if
[uploading usage statistics](#uploading-usage-statistics) is enabled).

Uploaded metadata consists of, for each organization hosted by the
installation:

- A subset of the basic metadata returned by the unauthenticated [`GET
/server_settings` API
  endpoint](https://zulip.com/api/get-server-settings).

  The purpose of that API endpoint is to serve the minimal data
  needed by the Zulip mobile apps in order to:

  - Verify that a given URL is indeed a valid Zulip server URL
  - Present a correct login form, offering only the supported features
    and authentication methods for that organization and Zulip server
    version.

  Most of the metadata it returns is necessarily displayed to anyone
  with network access to the Zulip server on the login and signup
  pages for your Zulip organization as well.

  (Some fields returned by this endpoint, like the organization icon
  and description, are not included in metadata uploaded for the Mobile
  Push Notification Service.)

- The [organization type](https://zulip.com/help/organization-type)
  and creation date.
- For the Mobile Push Notification Service, the number of user accounts
  with each role.

Our use of uploaded metadata is governed by the same [Terms of
Service](https://zulip.com/policies/terms) and [Privacy
Policy](https://zulip.com/policies/privacy) that cover Zulip services.

### Uploading usage statistics

By default, Zulip installations using the Mobile Push
Notification Service upload the following usage statistics. You can
disable these uploads any time by setting
`ZULIP_SERVICE_SUBMIT_USAGE_STATISTICS=False` in `/etc/zulip/settings.py`.

- Totals for messages sent and read with subtotals for various
  combinations of clients and integrations.
- Totals for active users under a few definitions (1day, 7day, 15day)
  and related statistics.

Some of the graphs on your server's [usage statistics
page](https://zulip.com/help/analytics) can be generated from these
statistics.

When enabled, usage statistics are submitted via an hourly cron
job. If you'd like to access plan management immediately after
enabling `SUBMIT_USAGE_STATISTICS=True` (the legacy form of this setting)
on a pre-8.0 Zulip server, you can run the analytics job manually via:

```
/home/zulip/deployments/current/manage.py update_analytics_counts
```

Our use of uploaded usage statistics is governed by the same [Terms of
Service](https://zulip.com/policies/terms) and [Privacy
Policy](https://zulip.com/policies/privacy) that cover Zulip services.

## Managing your registration

### Updating your server's registration

Your server's registration includes the server's hostname and contact
email address (from `EXTERNAL_HOST` and `ZULIP_ADMINISTRATOR` in
`/etc/zulip/settings.py`, aka the `--hostname` and `--email` options
in the installer). You can update your server's registration data by
running `manage.py register_server` again.

If you'd like to rotate your server's API key for this registration
(`zulip_org_key`), you need to use
`manage.py register_server --rotate-key` option; it will automatically
generate a new `zulip_org_key` and store that new key in
`/etc/zulip/zulip-secrets.conf`.

### Moving your registration to a new server

When migrating your Zulip deployment to a new machine, you will likely want to
retain your original registration and successfully transfer it. This is
especially important if you have an active plan for the Mobile Push
Notification Service.

The best way to preserve your registration when moving to a new server is to
copy over the credentials from the old server. These credentials are stored in
the `/etc/zulip/zulip-secrets.conf` file, specifically in the `zulip_org_id`
and `zulip_org_key` fields. After installing Zulip on the new machine, ensure
that `zulip_org_id` and `zulip_org_key` are set to the same values as on the
old server.

If you used the [official backup tool](export-and-import.md#backups)
to restore your Zulip deployment on the new machine, it will have
automatically transferred all secrets, including the registration
credentials, correctly.

#### Transferring your registration if you lost the original credentials

If you have lost your original credentials, you can still transfer your Zulip
registration to a new server by following these steps:

1. Ensure Zulip is installed and accessible:

   - Install Zulip on the new machine and ensure it is fully operational.
   - The server must be accessible on the hostname associated with the original
     registration, with properly configured SSL certificates.
   - This process **will not work** if your Zulip server is on a local network
     or otherwise unreachable from the internet by Zulip services.
     If that’s the case, contact
     [support@zulip.com](mailto:support@zulip.com) for assistance.

1. Run the below command to transfer your registration to the new server. This will
   execute a verification flow to prove to Zulip services that
   you control the hostname and upon success, re-generate the credentials for
   using the registration and write them to the `/etc/zulip/zulip-secrets.conf` file.

   ```bash
   /home/zulip/deployments/current/manage.py register_server --registration-transfer
   ```

   Note that the `zulip_org_key` value changes in the process, and therefore if you
   still have an old server running using these services, it will lose access upon
   execution of this command.

1. Apply the changes by restarting the server:

   ```bash
   /home/zulip/deployments/current/scripts/restart-server
   ```

   If you use the Mobile Push Notification Service,
   [verify][verify-push-notifications] that push notifications are working
   correctly. If you encounter further issues, contact
   [support@zulip.com](mailto:support@zulip.com).

1. If you store `/etc/zulip/zulip-secrets.conf` secrets externally in
   an external configuration management tool (Ansible, etc.), or
   [backups](export-and-import.md#backups), this is a good time to
   update that configuration.

[verify-push-notifications]: https://zulip.com/help/mobile-notifications#testing-mobile-notifications

### Deactivating your server's registration

If you are deleting your Zulip server or otherwise no longer want to
use any Zulip services, you can deactivate your server's registration.

1. [Cancel any paid
   plans](https://zulip.com/help/self-hosted-billing#cancel-paid-plan)
   associated with your server.

1. Run the deregistration command. If you installed Zulip directly on
   the server (without Docker), run as root:

   ```
   su zulip -c '/home/zulip/deployments/current/manage.py register_server --deactivate'
   ```

   Or if you're {doc}`using Docker <docker:index>`, run:

   ```
   cd docker-zulip
   ./manage.py register_server --deactivate
   ```

1. In `/etc/zulip/settings.py`, set any enabled `ZULIP_SERVICE_*`
   settings to `False`. If your server still uses the legacy
   `PUSH_NOTIFICATION_BOUNCER_URL` setting, comment out that line.
   Then [restart your Zulip
   server](settings.md#changing-server-settings).

If you ever need to reactivate your server's registration, [contact Zulip
support](https://zulip.com/help/contact-support).

### Pausing use of Zulip services

You can temporarily stop using a service by setting its `ZULIP_SERVICE_*`
setting to `False` in `/etc/zulip/settings.py`, and
[restarting your Zulip server](settings.md#changing-server-settings).
For example, set `ZULIP_SERVICE_PUSH_NOTIFICATIONS = False` to stop
mobile push notifications. To start using the service again, set it
back to `True` and restart your server.

To stop sharing usage statistics, also set
`ZULIP_SERVICE_SUBMIT_USAGE_STATISTICS = False`. If your server still
uses the legacy `PUSH_NOTIFICATION_BOUNCER_URL` setting, comment out
that line before restarting.
