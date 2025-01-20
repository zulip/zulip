# Zulip Zoom Integration

Make video calls from Zulip with Zoom!

### Using Zoom in your Zulip organization

!!! warn ""

    **Note**: If you are self-hosting, you will need to
    [create a Zoom application][build-app].

To configure your Zulip organization to create Zoom meetings using Zulip's
[call buttons](/help/start-a-call)
(<i class="zulip-icon zulip-icon-voice-call"></i> /
<i class="zulip-icon zulip-icon-video-call"></i>), set Zoom as your
organization's [video call provider][change-provider].

!!! tip ""

    The default video call provider is [Jitsi Meet][Jitsi Meet doc].

### Linking your Zoom account

The first time you click either of the [call buttons](/help/start-a-call)
(<i class="zulip-icon zulip-icon-voice-call"></i> /
<i class="zulip-icon zulip-icon-video-call"></i>) in Zulip, you will
automatically be prompted to link your Zoom account with your Zulip account.

### Unlinking your Zoom account

Log in to the [Zoom App Marketplace](https://marketplace.zoom.us/). Open
**Manage**, select **Added Apps**, click the **Remove** button next to the
Zulip app, and click **Confirm**.

[change-provider]: /help/start-a-call#change-your-call-provider
[build-app]: https://zulip.readthedocs.io/en/latest/production/video-calls.html#zoom
[Jitsi Meet doc]: /integrations/doc/jitsi
