from typing import TypedDict

# For integrations that don't have example webhook fixtures/payloads,
# we create an Zulip notification message content and topic here in
# order to generate an example screenshot to include in the documentation
# page for those integrations.


class ScreenshotContent(TypedDict):
    topic: str
    content: str


FIXTURELESS_INTEGRATIONS: list[str] = []
FIXTURELESS_SCREENSHOT_CONTENT: dict[str, list[ScreenshotContent]] = {
    key: [globals()[key.upper().replace("-", "_")]] for key in FIXTURELESS_INTEGRATIONS
}
