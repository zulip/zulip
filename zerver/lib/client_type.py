from typing import Final, Literal

from zerver.lib.user_agent import parse_user_agent

ClientType = Literal[
    "desktop",
    "mobile",
    "web",
    "terminal",
    "archiver",
    "content_mirror",
    "bot",
    "other",
]

HUMAN_CLIENT_TYPES: Final[frozenset[ClientType]] = frozenset(
    {
        "desktop",
        "mobile",
        "web",
        "terminal",
    }
)

_BROWSER_USER_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "mozilla",
        "chrome",
        "firefox",
        "safari",
        "edge",
        "edg",
        "opera",
        "mobile safari",
        "mobilesafari",
    }
)


def classify_client_name(client_name: str) -> ClientType | None:
    normalized_client_name = client_name.lower()

    if normalized_client_name == "website" or normalized_client_name in _BROWSER_USER_AGENTS:
        return "web"

    if normalized_client_name in {"zulipmobile", "zulipandroid", "zulipios", "android", "ios"}:
        return "mobile"

    if normalized_client_name in {"zulipelectron", "zulipdesktop", "zulipflutter"}:
        return "desktop"

    if normalized_client_name in {"zulipterminal", "terminal"}:
        return "terminal"

    if "mirror" in normalized_client_name:
        return "content_mirror"

    if "archive" in normalized_client_name:
        return "archiver"

    if "bot" in normalized_client_name or "webhook" in normalized_client_name:
        return "bot"

    if "script" in normalized_client_name or "api" in normalized_client_name:
        return "other"

    return None


def infer_client_type(
    *,
    client_type: ClientType | None,
    client_name: str,
    user_agent: str | None,
) -> ClientType:
    if client_type is not None:
        return client_type

    if user_agent is not None:
        parsed_user_agent = parse_user_agent(user_agent)
        user_agent_name = parsed_user_agent.get("name")
        if user_agent_name is not None:
            inferred_type_from_user_agent = classify_client_name(user_agent_name)
            if inferred_type_from_user_agent is not None:
                return inferred_type_from_user_agent

    inferred_type_from_client_name = classify_client_name(client_name)
    if inferred_type_from_client_name is not None:
        return inferred_type_from_client_name

    return "other"
