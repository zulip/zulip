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

### Create a Google Cloud OAuth 2.0 app

You need to create a Google Cloud OAuth 2.0 app with access to the Google
Meet REST API.

!!! warn ""

    **Note:** The Google Cloud OAuth 2.0 app requires choosing an audience type:

    - **Internal**: For applications restricted to users within your Google
      Workspace organization. Internal only makes sense if every Zulip user
      who will create calls has a Google account in that Workspace domain.
      Note that the OAuth sign-in uses the Google account the user picks in
      their browser — not their Zulip email. Otherwise (for example, if
      some users only have a personal Gmail account, or an account in a
      different Workspace organization), use **External**.

    - **External**: For applications available to any user. The app must
      go through [Google's OAuth verification](https://support.google.com/cloud/answer/13463073?hl=en&ref_topic=13460882&sjid=6878633552635075588-EU)
      to be usable beyond a small number of manually added test users. The
      OAuth consent screen brand verification process typically takes 2–3
      business days after you submit for verification.

{start_tabs}

1. Visit the [Google Cloud Console](https://console.cloud.google.com/) and
   create or select a project.

1. Enable the **Google Meet REST API** for your project under **APIs & Services >
   Library**.

1. Configure the **OAuth consent screen** under **APIs & Services > OAuth
   consent screen**:
    - Fill in the **App name** and **User support email**.
    - Choose the audience type as described above.
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
   to the **Client Secret** you noted down for your Google Cloud OAuth client.

1. In `/etc/zulip/settings.py`, set `VIDEO_GOOGLE_MEET_CLIENT_ID` to the
   **Client Secret** you noted down for your Google Cloud OAuth client.

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
