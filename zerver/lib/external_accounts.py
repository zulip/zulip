"""
This module stores data for "external account" custom profile field.
"""

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django_stubs_ext import StrPromise

from zerver.lib.types import ProfileFieldData
from zerver.lib.validator import (
    check_dict_only,
    check_external_account_url_pattern,
    check_required_string,
)


# Default external account fields are by default available
# to realm admins, where realm admin only need to select
# the default field and other values(i.e. name, url) will be
# fetch from this dictionary.
@dataclass
class ExternalAccount:
    text: str  # Field text for admins - custom profile field in org settings view
    name: StrPromise  # Field label or name - user profile in user settings view
    hint: str  # Field hint for realm users
    url_pattern: str  # Field URL linkifier


# Set url_pattern as "%(username)s" if there's no common URL pattern,
# and the user should enter the full URL of their link.
# Set url_pattern as "" to make the field a text field.
DEFAULT_EXTERNAL_ACCOUNTS = {
    "behance": ExternalAccount(
        text="Behance",
        url_pattern="https://www.behance.net/%(username)s",
        name=gettext_lazy("Behance username"),
        hint="",
    ),
    "bitbucket": ExternalAccount(
        text="Bitbucket",
        url_pattern="https://bitbucket.org/%(username)s",
        name=gettext_lazy("Bitbucket username"),
        hint="",
    ),
    "bluesky": ExternalAccount(
        text="Bluesky",
        url_pattern="https://bsky.app/profile/%(username)s",
        name=gettext_lazy("Bluesky handle"),
        hint="",
    ),
    "codeberg": ExternalAccount(
        text="Codeberg",
        url_pattern="https://codeberg.org/%(username)s",
        name=gettext_lazy("Codeberg username"),
        hint="",
    ),
    "discord": ExternalAccount(
        text="Discord",
        url_pattern="",
        name=gettext_lazy("Discord tag"),
        hint="",
    ),
    "dribbble": ExternalAccount(
        text="Dribbble",
        url_pattern="https://dribbble.com/%(username)s",
        name=gettext_lazy("Dribbble username"),
        hint="",
    ),
    "facebook": ExternalAccount(
        text="Facebook",
        url_pattern="https://www.facebook.com/%(username)s",
        name=gettext_lazy("Facebook username"),
        hint="",
    ),
    "github": ExternalAccount(
        text="GitHub",
        url_pattern="https://github.com/%(username)s",
        name=gettext_lazy("GitHub username"),
        hint="",
    ),
    "gitlab": ExternalAccount(
        text="GitLab",
        url_pattern="https://gitlab.com/%(username)s",
        name=gettext_lazy("GitLab username"),
        hint="",
    ),
    "instagram": ExternalAccount(
        text="Instagram",
        url_pattern="https://www.instagram.com/%(username)s",
        name=gettext_lazy("Instagram username"),
        hint="",
    ),
    "linkedin": ExternalAccount(
        text="LinkedIn",
        url_pattern="https://www.linkedin.com/in/%(username)s",
        name=gettext_lazy("LinkedIn profile name"),
        hint="",
    ),
    "mastodon": ExternalAccount(
        text="Mastodon",
        url_pattern="%(username)s",
        name=gettext_lazy("Mastodon profile"),
        hint="The full URL to your profile",
    ),
    "medium": ExternalAccount(
        text="Medium",
        url_pattern="https://%(username)s.medium.com",
        name=gettext_lazy("Medium username"),
        hint="",
    ),
    "pinterest": ExternalAccount(
        text="Pinterest",
        url_pattern="https://www.pinterest.com/%(username)s",
        name=gettext_lazy("Pinterest username"),
        hint="",
    ),
    "reddit": ExternalAccount(
        text="Reddit",
        url_pattern="https://www.reddit.com/user/%(username)s",
        name=gettext_lazy("Reddit username"),
        hint="",
    ),
    "snapchat": ExternalAccount(
        text="Snapchat",
        url_pattern="https://www.snapchat.com/@%(username)s",
        name=gettext_lazy("Snapchat username"),
        hint="",
    ),
    "threads": ExternalAccount(
        text="Threads",
        url_pattern="https://www.threads.com/@%(username)s",
        name=gettext_lazy("Threads username"),
        hint="",
    ),
    "tiktok": ExternalAccount(
        text="TikTok",
        url_pattern="https://www.tiktok.com/@%(username)s",
        name=gettext_lazy("TikTok username"),
        hint="",
    ),
    "twitch": ExternalAccount(
        text="Twitch",
        url_pattern="https://www.twitch.tv/%(username)s",
        name=gettext_lazy("Twitch username"),
        hint="",
    ),
    "x": ExternalAccount(
        text="X",
        url_pattern="https://x.com/%(username)s",
        name=gettext_lazy("X username"),
        hint="",
    ),
    "youtube": ExternalAccount(
        text="YouTube",
        url_pattern="https://www.youtube.com/%(username)s",
        name=gettext_lazy("YouTube handle"),
        hint="",
    ),
}


def get_default_external_accounts() -> dict[str, dict[str, str]]:
    return {
        subtype: {
            "text": external_account.text,
            "url_pattern": external_account.url_pattern,
            "name": str(external_account.name),
            "hint": external_account.hint,
        }
        for subtype, external_account in DEFAULT_EXTERNAL_ACCOUNTS.items()
    }


def validate_external_account_field_data(field_data: ProfileFieldData) -> ProfileFieldData:
    field_validator = check_dict_only(
        [("subtype", check_required_string)],
        [("url_pattern", check_external_account_url_pattern)],
    )
    field_validator("field_data", field_data)

    field_subtype = field_data.get("subtype")
    if field_subtype not in DEFAULT_EXTERNAL_ACCOUNTS and field_subtype != "custom":
        raise ValidationError(_("Invalid external account type"))

    return field_data
