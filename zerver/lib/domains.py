import re
from typing import Optional

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


def validate_domain(domain: Optional[str]) -> None:
    if domain is None or len(domain) == 0:
        raise ValidationError(_("Domain can't be empty."))
    if "." not in domain:
        raise ValidationError(_("Domain must have at least one dot (.)"))
    if len(domain) > 255:
        raise ValidationError(_("Domain is too long"))
    if domain[0] == "." or domain[-1] == ".":
        raise ValidationError(_("Domain cannot start or end with a dot (.)"))
    for subdomain in domain.split("."):
        if not subdomain:
            raise ValidationError(_("Consecutive '.' are not allowed."))
        if subdomain[0] == "-" or subdomain[-1] == "-":
            raise ValidationError(_("Subdomains cannot start or end with a '-'."))
        if not re.match(r"^[a-z0-9-]*$", subdomain):
            raise ValidationError(_("Domain can only have letters, numbers, '.' and '-'s."))
