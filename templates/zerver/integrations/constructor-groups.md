# Use Constructor Groups as your call provider in Zulip

You can configure [Constructor Groups][constructor-groups] as the call
provider for your organization. Users will be able to start a Constructor
Groups call and invite others using the **add video call**
(<i class="zulip-icon zulip-icon-video-call"></i>) button [in the compose
box](/help/start-a-call).

!!! warn ""

    **Note:** This is currently only possible on self-hosted Zulip
    installations, and requires a Constructor Groups account.

## Configure Constructor Groups as your call provider

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. You can configure Zulip to use
[Constructor Groups][constructor-groups] as your call provider instead.

{start_tabs}

1. Obtain your Constructor Groups [API credentials][constructor-groups-api-docs]
   by going to your Constructor Groups dashboard. Select **Settings**, and
   open the **Development** tab. Click the **Create new API Key** button,
   fill the required fields, and click **Create**. Copy your **Access Key**
   and **Secret Key** from the window that opens.

1. In `/etc/zulip/zulip-secrets.conf`, set `constructor_groups_access_key`
   and `constructor_groups_secret_key` to the access key and secret key
   created in the previous step.

1. In `/etc/zulip/settings.py`, set `CONSTRUCTOR_GROUPS_URL` to your
   Constructor Groups API URL, e.g., `https://example.constructor.app/api/groups/xapi`.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

{settings_tab|organization-settings}

1. Under **Compose settings**, select Constructor Groups from the
  **Call provider** dropdown.

1. Click **Save changes**.

{end_tabs}

### Related documentation

- [Constructor Groups API documentation][constructor-groups-api-docs]
- [How to start a call](/help/start-a-call)
- [Jitsi Meet integration](/integrations/jitsi)
- [Zoom integration](/integrations/zoom)
- [BigBlueButton integration](/integrations/big-blue-button)
- [Nextcloud Talk integration](/integrations/nextcloud-talk)

[constructor-groups-api-docs]: https://developer.perculus.com/v2-en
[constructor-groups]: https://constructor.tech/products/learning/groups
