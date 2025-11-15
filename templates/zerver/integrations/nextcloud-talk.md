  # Use Nextcloud Talk as your call provider in Zulip

  You can configure Nextcloud Talk as the call provider for your organization.
  Users will be able to start a Nextcloud Talk call and invite others using the
  **add video call** (<i class="zulip-icon zulip-icon-video-call"></i>) or
  **add voice call** (<i class="zulip-icon zulip-icon-voice-call"></i>) button
  [in the compose box](/help/start-a-call).

  !!! warn ""

      **Note:** This is currently only possible on self-hosted Zulip
      installations, and you'll need access to a Nextcloud server with
      the Talk app enabled.

  ## Configure Nextcloud Talk as your call provider

  By default, Zulip integrates with
  [Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
  source video conferencing solution. You can configure Zulip to use Nextcloud Talk
  as your call provider instead.

  {start_tabs}

  1. Log into your Nextcloud server with the user account that will be used
     for creating video call rooms.

  1. Generate an app password for API access:
     - Go to **Settings** → **Security** → **Devices & sessions**
     - In the "App name" field, enter a name like "Zulip Integration"
     - Click **Create new app password** and copy the generated password

  1. In `/etc/zulip/zulip-secrets.conf`, set `nextcloud_talk_password` to
     the app password you generated in the previous step.

  1. In `/etc/zulip/settings.py`, configure the following settings:

     NEXTCLOUD_SERVER = "https://nextcloud.example.com"
     NEXTCLOUD_TALK_USERNAME = "your-nextcloud-username"

  1. Restart the Zulip server with
    `/home/zulip/deployments/current/scripts/restart-server`.

  {settings_tab|organization-settings}

  1. Under **Compose settings**, select Nextcloud Talk from the Call provider
  dropdown.
  2. Click **Save changes**.

  {end_tabs}

## Related documentation

- [How to start a call](/help/start-a-call)
- [Jitsi Meet integration](/integrations/doc/jitsi)
- [BigBlueButton integration](/integrations/doc/big-blue-button)

