# GIF picker integrations

This page documents the server-level configuration required to enable
GIPHY or Tenor integrations to [add GIFs in your message][help-center-giphy] on
a self-hosted Zulip server.

:::{note}
If API keys are configured for both integrations, Zulip will prioritize Tenor.
In this case, the GIF picker will use Tenor instead of GIPHY.
:::

## GIPHY

To enable the GIPHY integration, you need to get a production API key from
[GIPHY](https://developers.giphy.com/).

### Apply for API key

1. [Create a GIPHY account](https://giphy.com/join).

1. Create a GIPHY API key by clicking “Create an App” on the
   [Developer Dashboard][giphy-dashboard].

1. Choose **SDK** as product type and click **Next Step**.

1. Enter a name and a description for your app and click on **Create
   New App**. The hostname for your Zulip server is a fine name.

1. You will receive a beta API key.

1. Apply for a production API key by following the steps mentioned by
   GIPHY on the same page. Note that when submitting a screenshot to
   request a production API key, GIPHY expects the screenshot to show
   the full page (including URL).

You can then configure your Zulip server to use GIPHY API as
follows:

1. In `/etc/zulip/settings.py`, enter your GIPHY API key as
   `GIPHY_API_KEY = "<Your API key from GIPHY>"`.

   GIPHY API keys are not secrets -- GIPHY expects every browser or
   other client connecting to your Zulip server will receive a copy --
   which is why they are configured in `settings.py` and not
   `zulip-secrets.conf`.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

Congratulations! You've configured the GIPHY integration for your
Zulip server. Your users can now use the integration as described in
[the help center article][help-center-giphy]. (A browser reload may
be required).

## Tenor

To enable the Tenor GIF integration, you will need to create
a production API key from Tenor.

### Create a Tenor API key

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/)
   and either sign in with an existing Google account or create a new one.

1. Choose an existing Google Cloud project where you want to enable the
   Tenor API, or create a new project if necessary.

1. In the Google Cloud Console, search for "Tenor API" in the search bar.

1. Select the Tenor API from the results and click "Enable" to activate
   it for your project.

1. After enabling the API, go to the "Credentials" section within your project.

1. Click "Create credentials" and choose "API Key" from the dropdown menu.

1. While configuring the API key, you can optionally restrict it to only
   call the Tenor API.

1. Store the newly generated API key.

You can then configure your Zulip server to use the Tenor API
as follows:

1. In `/etc/zulip/settings.py`, enter your Tenor API key as
   `TENOR_API_KEY = "<Your API key from the Google Cloud Console>"`.

   Just like GIPHY API keys, Tenor API keys are not secrets -- Tenor expects
   every browser or other client connecting to your Zulip server will
   receive a copy -- which is why they are configured in `settings.py` and not
   `zulip-secrets.conf`.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

Congratulations! You've configured the Tenor integration for your
Zulip server. Your users can now use the integration as described in
[the help center article][help-center-giphy]. (A browser reload may
be required).

[help-center-giphy]: https://zulip.com/help/animated-gifs-from-giphy
[giphy-dashboard]: https://developers.giphy.com/dashboard/
