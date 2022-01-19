# Start a video call

{start_tabs}

{!start-composing.md!}

1. Click the video-camera (<i class="fa fa-video-camera"></i>) icon in the
bottom left corner of the compose box. This will insert a link like
**[Click to join video call]\(https://meet.jit.si/123456789)** into the
compose box.

1. Send the message.

1. Click on the link in the message to start or join the call.

!!! tip ""

    You can replace "Click to join video call" with anything you want.

{end_tabs}

## Change your video call provider

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. Organization administrators can also
change the organization's video call provider. The video call providers
supported by zulip are:

* [Jitsi Meet](/integrations/doc/jitsi)
* [Zoom integration](/integrations/doc/zoom)
* [BigBlueButton integration](/integrations/doc/big-blue-button)

!!! tip ""

    It is also possible to disable the video call button for your organization by
    setting the provider to "None".

### Change your organization's video call provider

{start_tabs}

{settings_tab|organization-settings}

1. Under **Other settings** select appropriate provider from **Video call provider** dropdown.

1. Click **Save changes**.

{end_tabs}

[big-blue-button-configuration]: https://zulip.readthedocs.io/en/latest/production/video-calls.html#big-blue-button
[zoom-configuration]: https://zulip.readthedocs.io/en/latest/production/video-calls.html#zoom
