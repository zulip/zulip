By default, Zulip integrates with [Jitsi Meet](https://jitsi.org/jitsi-meet/),
a fully-encrypted, 100% open source video conferencing solution.

Zulip uses the [cloud version of Jitsi Meet](https://meet.jit.si/)
as its default video call provider. You can also use a self-hosted
instance of Jitsi Meet.

### Using Jitsi Meet

{settings_tab|organization-settings}

1. Under **Other settings**, select **Jitsi Meet** from the **Call provider**
   dropdown.

1. _(optional)_ Select **Custom URL** from the **Jitsi server URL** dropdown,
   and enter the URL of your self-hosted Jitsi Meet server. You can also set
   `JITSI_SERVER_URL` in `/etc/zulip/settings.py` to specify the server's URL.

1. Click **Save changes**, and use <kbd>Esc</kbd> to exit the settings.

1. [Open the compose box](/help/open-the-compose-box), and click the
   **video camera** (<i class="fa fa-video-camera"></i>) icon to insert
   a video call link, or the **phone** (<i class="fa fa-phone"></i>) icon
   to insert an audio call link into your message.

1. Send the message, and click on the link in the message to start or join
   the call.

!!! tip ""

    You can replace the call link label with any text you like.

[jitsi-server-url]: /help/start-a-call#configure-a-self-hosted-instance-of-jitsi-meet
