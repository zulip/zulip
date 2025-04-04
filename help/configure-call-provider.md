# Configure call provider

{!admin-only.md!}

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. Organization administrators can also
change the organization's call provider. The call providers
supported by Zulip are:

* [Jitsi Meet](/integrations/doc/jitsi)
* [Zoom integration](/integrations/doc/zoom)
* [BigBlueButton integration](/integrations/doc/big-blue-button)

!!! tip ""

    You can disable the video and voice call buttons for your organization
    by setting the **call provider** to "None".

## Configure your organization's call provider

{start_tabs}

{settings_tab|organization-settings}

1. Under **Compose settings**, select the desired provider from the
   **Call provider** dropdown.

{!save-changes.md!}

{end_tabs}

## Use a self-hosted instance of Jitsi Meet

Zulip uses the [cloud version of Jitsi Meet](https://meet.jit.si/)
as its default call provider. You can also use a self-hosted
instance of Jitsi Meet.

{start_tabs}

{settings_tab|organization-settings}

1. Under **Compose settings**, select **Custom URL** from the
   **Jitsi server URL** dropdown.

1. Enter the URL of your self-hosted Jitsi Meet server.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Start a call](/help/start-a-call)
* [Jitsi Meet integration](/integrations/doc/jitsi)
* [Zoom integration](/integrations/doc/zoom)
* [BigBlueButton integration](/integrations/doc/big-blue-button)
