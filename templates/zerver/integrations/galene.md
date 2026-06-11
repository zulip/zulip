# Use Galène as your call provider in Zulip

You can configure [Galène][galene] as the call provider for your
organization. Users will be able to start a call and invite others using the
**add video call** (<i class="zulip-icon zulip-icon-video-call"></i>) button
[in the compose box](/help/start-a-call).

!!! warn ""

    **Note:** This is currently only possible on self-hosted Zulip
    installations, and requires admin rights to a self-hosted Galène
    instance.

## Configure Galène as your call provider

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. You can configure Zulip to use
[Galène][galene] as your call provider instead.

{start_tabs}

1. [Install Galène][galene-install]. In `/etc/zulip/zulip-secrets.conf`, set
   `galene_admin_username` and `galene_admin_password`.

      !!! tip ""

        It is possible to set up multiple admin accounts in Galène, though it
        currently requires manual re-creation and merging of its `config.json`.
        Consider creating a dedicated "zulip" account.

1. In `/etc/zulip/settings.py`, set `GALENE_URL` to your Galène base URL,
   e.g., `https://galene.org:8443/`.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

{settings_tab|organization-settings}

1. Under **Compose settings**, select Galène from the **Call provider**
   dropdown.

1. Click **Save changes**.

{end_tabs}

### Related documentation

- [Galène documentation][galene-docs]
- [How to start a call](/help/start-a-call)
- [Jitsi Meet integration](/integrations/jitsi)
- [Zoom integration](/integrations/zoom)
- [BigBlueButton integration](/integrations/big-blue-button)
- [Constructor Groups integration](/integrations/constructor-groups)
- [Nextcloud Talk integration](/integrations/nextcloud-talk)

[galene]: https://galene.org
[galene-install]: https://galene.org/galene-install.html
[galene-docs]: https://github.com/jech/galene/blob/master/galene.md
