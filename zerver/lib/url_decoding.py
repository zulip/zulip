from urllib.parse import SplitResult, urlsplit

from django.conf import settings


def is_valid_near_link_recipient_encoding(recipient_encoding: str) -> bool:
    try:
        recipient_id, recipient_name = recipient_encoding.split("-", maxsplit=1)
    except ValueError:
        # Failed to decode the recipient encoding. Refer to
        # `encode_stream()` in url_encoding.py to see how we
        # encode recipient data for near links.
        return False

    recipient_name_is_encoded = all(char not in recipient_name for char in [" ", "%"])
    recipient_id_is_digits = all(id.isdigit() for id in recipient_id.split(","))

    return recipient_id_is_digits and recipient_name_is_encoded


def check_near_link_base(url: str) -> bool:
    """
    Performs basic checks to see whether or not the near link is
    from the same Zulip server and has a valid base structure.

    That is, they start with three main parts: a category
    (`narrow`), a section (`channel` or `dm`), and recipient
    encoding (e.g., `10-Denmark`, `11,12,20-group`).

    To match for a specific type of near link, use a function
    like `is_same_server_message_link`, which checks for
    additional parts the link might have.
    """
    split_result = urlsplit(url)
    fragment_parts = split_result.fragment.split("/")
    if split_result.hostname not in {None, settings.EXTERNAL_HOST_WITHOUT_PORT}:
        return False

    if len(fragment_parts) < 3:
        return False

    category = fragment_parts[0]
    section = fragment_parts[1]

    return (
        category == "narrow"
        and section in {"channel", "stream", "dm"}
        and is_valid_near_link_recipient_encoding(fragment_parts[2])
    )


def is_same_server_message_link(url: str) -> bool:
    """
    A message link is a type of near link that always ends with
    `/near/<message_id>`, where <message_id> is a sequence of
    digits. The URL fragment of a message link has at least 5
    parts. e.g. '#narrow/dm/9,15-dm/near/43'
    """
    if not check_near_link_base(url):
        return False
    fragment_parts = urlsplit(url).fragment.split("/")

    if len(fragment_parts) < 5:
        return False

    ends_with_near_message_id = fragment_parts[-2] == "near" and fragment_parts[-1].isdigit()

    return ends_with_near_message_id


class NearLinkHandler:
    """
    The NearLinkHandler is a helper class for editing
    and cleaning up near links.

    It can do basic operations such as splitting, fetching
    link parts, and reassembling. It also applies some near
    link related validations and clean-up operations.

    See `test_near_link_variations.json` for examples of
    links this class is intended to handle.
    """

    def __init__(self, near_link: str) -> None:
        if not check_near_link_base(near_link):
            raise AssertionError("This near link is either invalid or not from this server.")
        self.split_result: SplitResult
        self.patch_near_link(urlsplit(near_link))

    def clean_near_link(self, split_result: SplitResult) -> SplitResult:
        """
        This function fixes legacy near links (uses "stream"),
        and makes sure relative links starts with "/".
        """
        fragment_parts = split_result.fragment.split("/")
        changed_parts = {}

        if fragment_parts[1] == "stream":
            fragment_parts[1] = "channel"
        if split_result.hostname is None and split_result.path == "":
            # Makes sure a relative near link starts with "/"
            changed_parts["path"] = "/"

        fragments = "/".join(fragment_parts)
        changed_parts["fragment"] = fragments
        cleaned_split_result = split_result._replace(**changed_parts)
        return cleaned_split_result

    def get_url(self) -> str:
        return self.split_result.geturl()

    def patch_near_link(self, split_result: SplitResult) -> None:
        self.split_result = self.clean_near_link(split_result)

    def get_near_link_fragment_parts(self) -> list[str]:
        return self.split_result.fragment.split("/")

    def patch_near_link_fragment_parts(self, fragment_parts: list[str]) -> None:
        fragments = "/".join(fragment_parts)
        patched_split_result = self.split_result._replace(fragment=fragments)
        self.patch_near_link(patched_split_result)
