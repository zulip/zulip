# Zulip BigBlueButton integration

Zulip supports using [BigBlueButton](https://bigbluebutton.org/) as its
video call provider.

!!! warn ""

    **Note:** This is currently only possible on self-hosted Zulip
    installations, and you'll need a BigBlueButton server.

{start_tabs}

1. Run `bbb-conf --secret` on your BigBlueButton server to get
   the hostname and shared secret for your BigBlueButton server.

1. In `/etc/zulip/zulip-secrets.conf`, set `big_blue_button_secret` to your
   BigBlueButton server's shared secret.

1. In `/etc/zulip/settings.py`, set `BIG_BLUE_BUTTON_URL` to your
   BigBlueButton server's hostname.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

1. Select BigBlueButton as the organization's
   [video call provider][video call provider].

{end_tabs}

You're done! Zulip's [call button](/help/start-a-call) will now create
meetings using BigBlueButton.

### Related documentation

* [BigBlueButton server configuration](https://docs.bigbluebutton.org/administration/customize/#other-configuration-changes)

[video call provider]: /help/start-a-call#changing-your-organizations-video-call-provider
