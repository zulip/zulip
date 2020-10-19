# Start a video call

{start_tabs}

{!start-composing.md!}

2. Click the video-camera (<i class="fa fa-video-camera"></i>) icon in the
bottom left corner of the compose box. This will insert a link like
**[Click to join video call]\(https://meet.jit.si/123456789)** into the
compose box.

4. Send the message.

5. Click on the link in the message to start or join the call.

!!! warn ""
    **Note**: You can replace "Click to join video call" with anything you want.

{end_tabs}

## Change your video chat provider

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. Organization administrators can also
change the organization's video chat provider.

### Change your organization's video chat provider

{start_tabs}

{tab|jitsi-meet}

Zulip's default video chat provider is [Jitsi
Meet](https://meet.jit.si).

You can also use Zulip with Jitsi Meet on-premise; to configure this,
just set `JITSI_SERVER_URL` in `/etc/zulip/settings.py`.

{tab|bigbluebutton}

Using Big Blue Button as a video chat provider is currently only
possible on self-hosted Zulip installations.  See the [detailed
configuration instructions][big-blue-button-configuration].

{tab|zoom}

Zulip supports Zoom as the video chat provider using an OAuth
integration.  You can set it up as follows:

{settings_tab|organization-settings}

1. Under **Other settings** set **Video chat provider** to **Zoom**.

1. Click **Save changes**.

Any user who creates a video call link using the instructions above
will be prompted to link a Zoom account with their Zulip account.

If you would like to unlink Zoom from your Zulip account:

1. Log in to the [Zoom App Marketplace](https://marketplace.zoom.us/).

1. Click **Manage** → **Installed Apps**.

1. Click the **Uninstall** button next to the Zulip app.

If you are self-hosting, you will need to [create a Zoom
application][zoom-configuration] to use this integration.

{tab|disable}

You can also disable the video call button for your organization by
setting the provider to "None".

{end_tabs}

[big-blue-button-configuration]: https://zulip.readthedocs.io/en/latest/production/video-calls.html#big-blue-button
[zoom-configuration]: https://zulip.readthedocs.io/en/latest/production/video-calls.html#zoom
