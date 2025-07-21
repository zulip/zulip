from typing import TypedDict

# For integrations that don't have example webhook fixtures/payloads,
# we create an Zulip notification message content and topic here in
# order to generate an example screenshot to include in the documentation
# page for those integrations.


class ScreenshotContent(TypedDict):
    topic: str
    content: str
