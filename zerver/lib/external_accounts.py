"""
    This module stores data for "External Account" custom profile field.
"""
from typing import Optional
from django.utils.translation import ugettext as _

from zerver.lib.validator import check_required_string, \
    check_external_account_url_pattern, check_dict_only
from zerver.lib.types import ProfileFieldData

DEFAULT_EXTERNAL_ACCOUNTS = {
    "twitter": {
        "text": "Twitter",
        "url_pattern": "https://twitter.com/%(username)s"
    },
    "github": {
        "text": 'GitHub',
        "url_pattern": "https://github.com/%(username)s"
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
