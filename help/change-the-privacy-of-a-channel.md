# Change the privacy of a channel

{!channel-privacy-types.md!}

Organization administrators and [channel
administrators](/help/configure-who-can-administer-a-channel) can always make a
channel private. However, they can only make a private channel public or
web-public if they have content access to it:

{!content-access-definition.md!}

!!! warn ""

    **Warning**: Be careful making a private channel public. All past messages
    will become accessible, even if the channel previously had protected history.

{start_tabs}

{tab|desktop-web}

{relative|channel|all}

1. Select a channel.

{!select-channel-view-general.md!}

1. Under **Channel permissions**, configure **Who can access the channel**.

{!save-changes.md!}

{!channel-settings-general-tab-tip.md!}

{tab|mobile}

Access this feature by following the web app instructions in your
mobile device browser.

Implementation of this feature in the mobile app is tracked [on
GitHub](https://github.com/zulip/zulip-flutter/issues/1102). If
you're interested in this feature, please react to the issue's
description with 👍.

{end_tabs}

{!automated-notice-channel-event.md!}

## Related articles

* [Channel permissions](/help/channel-permissions)
* [Channel posting policy](/help/channel-posting-policy)
* [Configure who can administer a channel](/help/configure-who-can-administer-a-channel)
