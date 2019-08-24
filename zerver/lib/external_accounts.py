"""
    This module stores data for "External Account" custom profile field.
"""
from typing import Optional
from django.utils.translation import ugettext as _

from zerver.lib.validator import check_required_string, \
    check_external_account_url_pattern, check_dict_only
from zerver.lib.types import ProfileFieldData

# Default external account fields are by default avaliable
# to realm admins, where realm admin only need to select
# the default field and other values(i.e. name, url) will be
# fetch from this dictionary.
# text: Field text for admins - custom profile field in org settngs view
# name: Field label or name - user profile in user settings view
# hint: Field hint for realm users
# url_patter: Field url linkifier
DEFAULT_EXTERNAL_ACCOUNTS = {
    "twitter": {
        "text": "Twitter",
        "url_pattern": "https://twitter.com/%(username)s",
        "name": "Twitter",
        "hint": "Enter your Twitter username",
    },
    "github": {
        "text": 'GitHub',
        "url_pattern": "https://github.com/%(username)s",
        "name": "GitHub",
        "hint": "Enter your GitHub username",
    },
}

def validate_external_account_field_data(field_data: ProfileFieldData) -> Optional[str]:
    field_validator = check_dict_only(
        [('subtype', check_required_string)],
        [('url_pattern', check_external_account_url_pattern)],
    )
    error = field_validator('field_data', field_data)
    if error:
        return error

    field_subtype = field_data.get('subtype')
    if field_subtype not in DEFAULT_EXTERNAL_ACCOUNTS.keys():
        if field_subtype == "custom":
            if 'url_pattern' not in field_data.keys():
                return _("Custom external account must define url pattern")
        else:
            return _("Invalid external account type")

    return None
