# Use Google Meet as your call provider in Zulip

You can configure Google Meet as the call provider for your organization. Users
will be able to start a Google Meet call and invite others using the **add video
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

### Create a Google Cloud OAuth 2.0 app

You need to create a Google Cloud OAuth 2.0 app with access to the [Google
Meet REST API][google-meet-api].

!!! warn ""

    **Note**: There are two **Audience** types for Google Cloud OAuth 2.0
    apps:

    - **Internal**: Zulip users will need to have an account in the Google
      Workspace organization associated with your Google Cloud OAuth app in
      order to create calls.

    - **External**: Zulip users will need to have a Google account in order
      to create calls, and your Google Cloud OAuth app must go through
      [Google's OAuth verification][google-app-verification].

{start_tabs}

1. Visit the [Google Cloud Console](https://console.cloud.google.com/), and
   create or select a project.

1. Enable the **Google Meet REST API** for your project under
   **APIs & Services > Library**.

1. Configure the **OAuth consent screen** under **APIs & Services > OAuth
   consent screen**:
    - Fill in the **App name** and **User support email**.
    - Choose the **Audience** type: **Internal** or **External**.
    - Add **Developer contact information**.

1. If you selected **External** as the **Audience** type, click **Data
   Access > Add or Remove Scopes** and add the
   `https://www.googleapis.com/auth/meetings.space.created` scope.

1. Under **APIs & Services > Credentials**, click **Create Credentials** and
   select **OAuth client ID**:
    - Choose **Web application** as the application type.
    - Under **Authorized redirect URIs**, add
      `https://zulip.example.com/calls/google_meet/complete`, replacing
      `zulip.example.com` with your Zulip organization's URL.
    - Note down the **Client ID** and **Client Secret** shown after creation.

{end_tabs}

### Configure your Zulip server and organization

{start_tabs}

1. In `/etc/zulip/zulip-secrets.conf`, set `video_google_meet_client_secret`
   to the **Client Secret** you noted down for your Google Cloud OAuth app.

1. In `/etc/zulip/settings.py`, set `VIDEO_GOOGLE_MEET_CLIENT_ID` to the
   **Client Secret** you noted down for your Google Cloud OAuth app.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

{settings_tab|organization-settings}

1. Under **Compose settings**, select Google Meet from the **Call provider**
   dropdown.

1. Click **Save changes**.

{end_tabs}

## Related documentation

- [How to start a call](/help/start-a-call)
- [Google Meet REST API documentation][google-meet-api]
- [Jitsi Meet integration](/integrations/jitsi)
- [BigBlueButton integration](/integrations/big-blue-button)
- [Webex integration](/integrations/webex)
- [Zoom integration](/integrations/zoom)
- [Constructor Groups integration](/integrations/constructor-groups)
- [Nextcloud Talk integration](/integrations/nextcloud-talk)

[google-app-verification]: https://support.google.com/cloud/answer/13463073?hl=en&ref_topic=13460882&sjid=6878633552635075588-EU
[google-meet-api]: https://developers.google.com/workspace/meet/api/reference/rest
