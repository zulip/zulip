# Use BigBlueButton as your call provider in Zulip

You can configure BigBlueButton as the call provider for your organization.
Users will be able to start a BigBlueButton call and invite others using the
**add video call** (<i class="zulip-icon zulip-icon-video-call"></i>) or
**add voice call** (<i class="zulip-icon zulip-icon-voice-call"></i>) button
[in the compose box](/help/start-a-call).

!!! warn ""

    **Note:** This is currently only possible on self-hosted Zulip
    installations, and you'll need a BigBlueButton server.

## Configure BigBlueButton as your call provider

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. You can configure Zulip to use BigBlueButton
as your call provider instead.

{start_tabs}

1. Run `bbb-conf --secret` on your BigBlueButton server to get
   the hostname and shared secret for your BigBlueButton server.

1. In `/etc/zulip/zulip-secrets.conf`, set `big_blue_button_secret` to your
   BigBlueButton server's shared secret.

1. In `/etc/zulip/settings.py`, set `BIG_BLUE_BUTTON_URL` to your
   BigBlueButton server's hostname.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

{settings_tab|organization-settings}

1. Under **Compose settings**, select BigBlueButton from the **Call provider**
   dropdown.

1. Click **Save changes**.

{end_tabs}

### Related documentation

- [How to start a call](/help/start-a-call)
- [Jitsi Meet integration](/integrations/doc/jitsi)
- [Zoom integration](/integrations/doc/zoom)
* [BigBlueButton server configuration](https://docs.bigbluebutton.org/administration/customize/#other-configuration-changes)
