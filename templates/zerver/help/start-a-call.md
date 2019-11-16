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

Note that the Google Hangouts integration requires a paid Google G
Suite account.

### Change your organization's video chat provider

{start_tabs}

{tab|google-hangouts}

{settings_tab|organization-settings}

1. Under **Other settings** set **Video chat provider** to **Google Hangouts**.

1. Enter the domain for your [G Suite team](https://gsuite.google.com/).

1. Click **Save changes**.

{tab|zoom}

{settings_tab|organization-settings}

1. Under **Other settings** set **Video chat provider** to **Zoom**.

1. Click **Save changes**.

Any user who creates a video call link using the instructions above
will be prompted to link a Zoom account with their Zulip account.

If you would like to unlink Zoom from your Zulip account:

1. Log in to the [Zoom App Marketplace](https://marketplace.zoom.us/).

1. Click **Manage** → **Installed Apps**.

1. Click the **Uninstall** button next to the Zulip app.

{tab|jitsi-on-premise}

If you're running both Zulip and Jitsi Meet on-premise, just set
`JITSI_SERVER_URL` in `/etc/zulip/settings.py`.

You can also disable the video call button for your community by
setting the provider to "None".

{end_tabs}
