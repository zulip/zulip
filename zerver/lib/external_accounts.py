"""
    This module stores data for "external account" custom profile field.
"""
from dataclasses import dataclass
from typing import Dict

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


DEFAULT_EXTERNAL_ACCOUNTS = {
    "twitter": ExternalAccount(
        text="Twitter",
        url_pattern="https://twitter.com/%(username)s",
        name=gettext_lazy("Twitter username"),
        hint="",
    ),
    "github": ExternalAccount(
        text="GitHub",
        url_pattern="https://github.com/%(username)s",
        name=gettext_lazy("GitHub username"),
        hint="",
    ),
}


def get_default_external_accounts() -> Dict[str, Dict[str, str]]:
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
    if field_subtype not in DEFAULT_EXTERNAL_ACCOUNTS:
        if field_subtype == "custom":
            if "url_pattern" not in field_data:
                raise ValidationError(_("Custom external account must define URL pattern"))
        else:
            raise ValidationError(_("Invalid external account type"))

    return field_data
