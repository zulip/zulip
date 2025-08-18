# Constructor Groups calls

{!admin-only.md!}

Constructor Groups is a video conferencing platform that can be integrated with Zulip to provide seamless video and voice calling directly from your chat interface.

!!! warn ""

    **Note:** Constructor Groups integration requires server-level configuration by a system administrator before it can be used.

## How Constructor Groups integration works

When Constructor Groups is configured as your organization's call provider:

1. **Smart room reuse**: The system automatically searches for existing Constructor Groups rooms with "Zulip" in the name associated with your email address.

2. **Automatic room creation**: If no existing room is found, a new room is created with the naming convention `"{Your Name}'s Zulip Videoconferencing Room"`.

3. **Seamless access**: Room links are automatically inserted into your messages, allowing participants to join with a single click.

## Start a Constructor Groups call

{start_tabs}

{tab|desktop-web}

{!start-composing.md!}

1. Click the **Add video call** (<i class="zulip-icon zulip-icon-video-call"></i>)
   icon at the bottom of the compose box. The system will automatically search
   for your existing Constructor Groups rooms, create a new room if none exists,
   and insert the room link into your message.

1. Send the message to share the call link with participants.

1. Click on the link in the message to start or join the call.

!!! tip ""

    Your Constructor Groups rooms are automatically reused across multiple
    conversations, maintaining consistency for your meetings.

{tab|mobile}

Access this feature by following the web app instructions in your
mobile device browser.

Implementation of Constructor Groups calls in the mobile app follows
the same pattern as other video call providers.

{end_tabs}

## Benefits of Constructor Groups integration

* **Room persistence**: Your Constructor Groups rooms are reused across multiple Zulip conversations, maintaining consistency for your meetings.

* **Professional naming**: Rooms are automatically named with a professional convention that identifies them as Zulip-generated meetings.

* **No separate authentication**: Uses your organization's Constructor Groups configuration without requiring individual user setup.

* **Seamless workflow**: Start calls directly from Zulip without switching applications or copying links.

## Troubleshooting Constructor Groups calls

### Constructor Groups doesn't appear as a call provider option

If Constructor Groups doesn't appear in your organization's call provider dropdown:

* **Server configuration required**: Contact your system administrator to configure Constructor Groups at the server level.
* **Restart needed**: The server may need to be restarted after configuration changes.

### "Constructor Groups is not configured" error

This error appears when:

* The server administrator hasn't completed the Constructor Groups configuration
* The integration requires server-level setup before it can be used
* Contact your system administrator for assistance

### "Failed to create video call" error

This typically indicates:

* **Invalid credentials**: The API credentials may be incorrect or expired
* **Network connectivity**: The server cannot reach Constructor Groups API endpoints  
* **Permissions**: The API credentials may lack necessary permissions

Contact your system administrator to verify the server configuration.

### Room creation is slow

Constructor Groups integration performs API calls to search for existing rooms and create new ones if needed. This process may take a few seconds, especially on the first use.

## Related articles

* [Start a call](/help/start-a-call)
* [Configure call provider](/help/configure-call-provider)
* [Constructor Groups integration](/integrations/doc/constructor-groups)