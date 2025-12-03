# Zulip Nextcloud integration

Send Nextcloud files in Zulip messages as uploaded files, public shared links, or internal shared links.

## Setup

1. **Create a Zulip bot user** and download its `zuliprc` file.  
   - In your Zulip organization, go to **Settings → Organization → Bots → Add a new bot**.  
   - Download the bot’s `zuliprc` file—it contains your **bot email** and **API key**.

2. **Install the Nextcloud Zulip app** from the [Nextcloud App Store](https://apps.nextcloud.com/apps/integration_zulip).

3. **Configure the app** inside Nextcloud using the following fields:
   - **Zulip instance URL:** your Zulip organization URL (e.g., `https://chat.example.com`)
   - **Email:** the bot user’s email
   - **API key:** the bot’s API key

## Usage

After setup, you can send files directly from Nextcloud into Zulip.  
Messages will appear in the configured stream or private conversation with the attached file or shared link.
