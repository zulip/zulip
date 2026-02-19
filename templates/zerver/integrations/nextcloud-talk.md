# Use Nextcloud Talk as your call provider in Zulip

You can configure Nextcloud Talk as the call provider for your organization.
Users will be able to start a Nextcloud Talk call and invite others using the
**add video call** (<i class="zulip-icon zulip-icon-video-call"></i>) button
[in the compose box](/help/start-a-call).

You'll need a Nextcloud server with the Talk app enabled.

!!! warn ""

    **Note:** This integration is not available in Zulip Cloud.

## Configure Nextcloud Talk as your call provider

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. You can configure Zulip to use Nextcloud
Talk as your call provider instead.

!!! warn ""

    **Note:** Zulip creates public Nextcloud Talk conversations with guest
    access, allowing anyone to join by visiting a URL and entering their
    name. This ensures that all Zulip users can join calls regardless of
    whether they have Nextcloud accounts.

{start_tabs}

1. Log in to your Nextcloud server with the user account that will be
   used for creating video call rooms. Using a dedicated account for
   this purpose is recommended.

1. Generate an app password in Nextcloud Talk for API access:
    - Go to your **Settings**, select **Personal Security** and navigate to
    the **Devices & sessions** section.
    - Set the **App name** to a name of your choice, such as `Zulip`.
    - Click **Create new app password**, and copy the generated password.

1. In `/etc/zulip/zulip-secrets.conf`, set `NEXTCLOUD_TALK_USERNAME` to your
   Nextcloud Talk username and `NEXTCLOUD_TALK_PASSWORD` to the app password
   you generated in the previous step.

1. In `/etc/zulip/settings.py`, set `NEXTCLOUD_SERVER` to the URL of your
   Nextcloud server.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

{settings_tab|organization-settings}

1. Under **Compose settings**, select Nextcloud Talk from the
   **Call provider** dropdown.

1. Click **Save changes**.

{end_tabs}

## Related documentation

- [How to start a call](/help/start-a-call)
- [Jitsi Meet integration](/integrations/jitsi)
- [Zoom integration](/integrations/zoom)
- [BigBlueButton integration](/integrations/big-blue-button)
- [Constructor Groups integration](/integrations/constructor-groups)
