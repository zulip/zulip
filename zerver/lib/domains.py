from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _, ugettext as err_

import re
from typing import Text

def validate_domain(domain):
    # type: (Text) -> None
    if domain is None or len(domain) == 0:
        raise ValidationError(_("Domain can't be empty."))
    if '.' not in domain:
        raise ValidationError(_("Domain must have at least one dot (.)"))
    if domain[0] == '.' or domain[-1] == '.':
        raise ValidationError(_("Domain cannot start or end with a dot (.)"))
    for subdomain in domain.split('.'):
        if not subdomain:
            raise ValidationError(_("Consecutive '.' are not allowed."))
        if subdomain[0] == '-' or subdomain[-1] == '-':
            raise ValidationError(_("Subdomains cannot start or end with a '-'."))
        if not re.match('^[a-z0-9-]*$', subdomain):
            raise ValidationError(_("Domain can only have letters, numbers, '.' and '-'s."))
