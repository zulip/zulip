# Use Google Meet as your call provider in Zulip

You can configure Google Meet as the call provider for your organization. Users
will be able to start a Google Meet and invite others using the **add video
call** (<i class="zulip-icon zulip-icon-video-call"></i>) button [in the
compose box](/help/start-a-call).

!!! warn ""

    **Note:** This is currently only possible on self-hosted Zulip
    installations.

## Configure Google Meet as your call provider

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. You can configure Zulip to use Google Meet
as your call provider instead.

### Create a Google Cloud OAuth 2.0 client

{start_tabs}

1. Visit the [Google Cloud Console](https://console.cloud.google.com/) and
   create or select a project.

1. Enable the **Google Meet REST API** for your project under **APIs & Services >
   Library**.

1. Configure the **OAuth consent screen** under **APIs & Services > OAuth
   consent screen**:
    - Fill in the **App name** and **User support email**.
    - Choose **External** as the audience type (or **Internal** if you are using a
      Google Workspace organization and want to restrict access to users within
      your organization).
    - Add **Developer contact information**.

1. If creating an app for use outside of your Google Workspace organization,
   click **Data Access > Add or Remove Scopes** and add the
   `https://www.googleapis.com/auth/meetings.space.created` scope.

1. Under **APIs & Services > Credentials**, click **Create Credentials** and
   select **OAuth client ID**.
    - Choose **Web application** as the application type.
    - Under **Authorized redirect URIs**, add
      `https://zulip.example.com/calls/google_meet/complete`, replacing
      `zulip.example.com` with your Zulip organization's URL.
    - Note the **Client ID** and **Client Secret** shown after creation.

{end_tabs}

### Configure your Zulip server and organization

{start_tabs}

1. In `/etc/zulip/zulip-secrets.conf`, set `video_google_meet_client_secret`
   to your OAuth client's "Client Secret".

1. In `/etc/zulip/settings.py`, set `VIDEO_GOOGLE_MEET_CLIENT_ID` to your
   OAuth client's "Client ID".

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

{settings_tab|organization-settings}

1. Under **Compose settings**, select Google Meet from the **Call provider**
   dropdown.

1. Click **Save changes**.

{end_tabs}

## Related documentation

- [How to start a call](/help/start-a-call)
- [Google Meet REST API documentation](https://developers.google.com/workspace/meet/api/reference/rest)
- [Jitsi Meet integration](/integrations/jitsi)
- [BigBlueButton integration](/integrations/big-blue-button)
- [Webex integration](/integrations/webex)
- [Zoom integration](/integrations/zoom)
- [Constructor Groups integration](/integrations/constructor-groups)
- [Nextcloud Talk integration](/integrations/nextcloud-talk)
