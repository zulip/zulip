# Use Galène as your call provider in Zulip

You can configure [Galène][galene] as the call
provider for your organization. Users will be able to start a
call and invite others using the **add video call**
(<i class="zulip-icon zulip-icon-video-call"></i>) button [in the compose
box](/help/start-a-call).

!!! warn ""

    **Note:** This is currently only possible on self-hosted Zulip
    installations, and requires admin rights a self-hosted Galène instance.

## Configure Galène as your call provider

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. You can configure Zulip to use
[Galène][galene] as your call provider instead.

{start_tabs}

1. [Install Galène][galene-install] and note the admin username/password you set,
   or obtain them from whoever set up the Galène instance you plan to use.
   If you have lost them and need to reset them, use `galenectl` as described
   in the docs to make a new `config.json` and then manually merge it with your
   existing `data/config.json`. It is possible to set up multiple admin accounts
   in Galène -- consider creating a "zulip" account.

1. In `/etc/zulip/zulip-secrets.conf`, set `galene_admin_username`
   and `galene_admin_password`
  <!-- TODO: support galene_admin_token once that exists -->

1. In `/etc/zulip/settings.py`, set `GALENE_URL` to your
   Galene base URL, e.g., `https://galene.org:8443/`.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

{settings_tab|organization-settings}

1. Under **Compose settings**, select Galène from the
  **Call provider** dropdown.

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
