[Jitsi Meet](https://jitsi.org/jitsi-meet/) is Zulip's default video
call provider. Jitsi Meet is a fully-encrypted, 100% open source video
conferencing solution.

### Using Jitsi Meet

1. Set Jitsi as the organization's [video call
   provider](/help/start-a-call#changing-your-organizations-video-call-provider),
   if it isn't already.

2. Zulip's [call button](/help/start-a-call) will now create meetings
   using Jitsi Meet.

Zulip's default video call provider is the cloud version of [Jitsi
Meet](https://meet.jit.si/) but it also possible to use Zulip with a
self-hosted instance of Jitsi Meet; to configure this, just set
`JITSI_SERVER_URL` in `/etc/zulip/settings.py`.
