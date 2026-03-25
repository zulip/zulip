# Use Webex as your call provider in Zulip

You can configure Webex as the call provider for your organization. Users will be
able to start a Webex meeting and invite others using the **add video call** (<i
class="zulip-icon zulip-icon-video-call"></i>) button [in the compose
box](/help/start-a-call).

!!! warn ""

    **Note:** This is currently only possible on self-hosted Zulip
    installations.

## Configure Webex as your call provider

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. You can configure Zulip to use Webex as your
call provider instead.

!!! warn ""

    For users in paid Webex organizations, which have the ability to create
    public rooms that are visible to every member within that organization,
    an ad-hoc meeting is created in Webex. Otherwise, for users of free
    Webex organizations, a personal room meeting is created in Webex.

### Create a custom Webex integration

{start_tabs}

1. Visit the [New Integration](https://developer.webex.com/my-apps/new/integration)
   page on the Webex developer portal.

1. Select "No" for "Will this integration use a mobile SDK?".

1. Fill in the **Integration name**, **Icon** and **App Hub Description**
   according to your preferences.

1. For **Redirect URI(s)**, enter `https://zulip.example.com/calls/webex/complete`
   replacing `zulip.example.com` with your Zulip organization's URL.

1. For **Scopes**, select `spark:all`, `meeting:schedules_read` and
   `meeting:schedules_write`, and select **Add Integration**.

1. _optional_: You can submit the integration to the [Webex App Hub](https://apphub.webex.com/)
   by following [this documentation](https://developer.webex.com/create/docs/app-hub-submission-process).

{end_tabs}

### Configure your Zulip server and organization

{start_tabs}

1. In `/etc/zulip/zulip-secrets.conf`, set `video_webex_client_secret`
   to your app's "Client Secret".

1. In `/etc/zulip/settings.py`, set `VIDEO_WEBEX_CLIENT_ID` to your
   app's "Client ID".

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

{settings_tab|organization-settings}

1. Under **Compose settings**, select Webex from the **Call provider**
   dropdown.

1. Click **Save changes**.

{end_tabs}

## Related documentation

- [How to start a call](/help/start-a-call)
- [Webex's developer documentation](https://developer.webex.com/create/docs/integrations)
- [Jitsi Meet integration](/integrations/jitsi)
- [BigBlueButton integration](/integrations/big-blue-button)
- [Constructor Groups integration](/integrations/constructor-groups)
- [Nextcloud Talk integration](/integrations/nextcloud-talk)
