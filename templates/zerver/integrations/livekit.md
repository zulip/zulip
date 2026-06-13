# Use LiveKit as your call provider in Zulip

You can configure [LiveKit](https://livekit.io/) as the call provider for
your organization. Users will be able to start a LiveKit call and invite
others using the **add video call**
(<i class="zulip-icon zulip-icon-video-call"></i>) button [in the compose
box](/help/start-a-call).

LiveKit is an open-source WebRTC SFU (Selective Forwarding Unit) that
provides scalable, low-latency video and voice calls hosted on your own
infrastructure.

!!! warn ""

    **Note:** This integration is not available in Zulip Cloud.

## Configure LiveKit as your call provider

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. You can configure Zulip to use
LiveKit as your call provider instead.

{start_tabs}

1. Set up a LiveKit server. You can [self-host
   LiveKit](https://docs.livekit.io/home/self-hosting/deployment/) or use
   [LiveKit Cloud](https://cloud.livekit.io/). If you manage your Zulip
   server with Puppet, an optional `zulip::profile::livekit` profile is
   available to install and run LiveKit alongside Zulip.

!!! warn ""

    **Note:** If you self-host LiveKit, ensure these ports are accessible: TCP
   `7880` (signal server / WebSocket), TCP `7881` (RTC over TCP), and
   UDP `50000`–`60000` (WebRTC media).

1. Obtain an API key and secret for your LiveKit server.

1. In `/etc/zulip/zulip-secrets.conf`, set `livekit_api_key` and
   `livekit_api_secret` to your LiveKit server's API key and secret.

1. In `/etc/zulip/settings.py`, set `LIVEKIT_URL` to your LiveKit
   server's WebSocket URL, e.g., `"wss://livekit.example.com"`.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

{settings_tab|organization-settings}

1. Under **Compose settings**, select LiveKit from the
   **Call provider** dropdown.

1. Click **Save changes**.

{end_tabs}

## Related documentation

- [How to start a call](/help/start-a-call)
- [Jitsi Meet integration](/integrations/jitsi)
- [Zoom integration](/integrations/zoom)
- [BigBlueButton integration](/integrations/big-blue-button)
- [Constructor Groups integration](/integrations/constructor-groups)
- [Nextcloud Talk integration](/integrations/nextcloud-talk)
- [Webex integration](/integrations/webex)
