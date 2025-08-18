# Use Constructor Groups as your call provider in Zulip

You can configure Constructor Groups as the call provider for your organization.
Users will be able to start a Constructor Groups call and invite others using the
**add video call** (<i class="zulip-icon zulip-icon-video-call"></i>) button
[in the compose box](/help/start-a-call).

!!! warn ""

    **Note:** This is currently only possible on self-hosted Zulip
    installations, and you'll need Constructor Groups API access.

## Configure Constructor Groups as your call provider

By default, Zulip integrates with
You can configure Zulip to use Constructor Groups as your call provider instead.

{start_tabs}

1. Obtain your Constructor Groups API credentials (access key, secret key, and API URL)
   from your Constructor Groups account.

1. In `/etc/zulip/zulip-secrets.conf`, set the following:
   ```
   constructor_groups_access_key = "your-access-key"
   constructor_groups_secret_key = "your-secret-key"
   ```

1. In `/etc/zulip/settings.py`, set `CONSTRUCTOR_GROUPS_URL` to your
   Constructor Groups API URL.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

{settings_tab|organization-settings}

1. Under **Compose settings**, select Constructor Groups from the **Call provider**
   dropdown.

1. Click **Save changes**.

{end_tabs}

### Related documentation

- [Constructor Groups calls](/help/constructor-groups-calls)
- [How to start a call](/help/start-a-call)
- [Jitsi Meet integration](/integrations/doc/jitsi)
- [Zoom integration](/integrations/doc/zoom)
- [BigBlueButton integration](/integrations/doc/big-blue-button)
