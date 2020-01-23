'''
This module defines some custom url validation regexes/utilities.
'''

def get_uncompiled_netloc_re() -> str:
    '''
    From: https://docs.djangoproject.com/en/3.0/_modules/django/core/validators/#URLValidator

    This method takes code from Django's URLValidator. We cannot use the URLValidator as is
    because it performs checks on the scheme as well and we have code to deal with schemes
    already that doesn't agree with URLValidator. Thus, we extract the netloc specific parts
    of URLValidator here.
    '''

    ul = '\u00a1-\uffff'  # unicode letters range (must not be a raw string)

    # IP patterns
    ipv4_re = r'(?:25[0-5]|2[0-4]\d|[0-1]?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}'
    ipv6_re = r'\[[0-9a-f:\.]+\]'  # (simple regex, validated later)

    # Host patterns
    hostname_re = r'[a-z' + ul + r'0-9](?:[a-z' + ul + r'0-9-]{0,61}[a-z' + ul + r'0-9])?'
    # Max length for domain name labels is 63 characters per RFC 1034 sec. 3.1
    domain_re = r'(?:\.(?!-)[a-z' + ul + r'0-9-]{1,63}(?<!-))*'
    tld_re = (
        r'\.'                                # dot
        r'(?!-)'                             # can't start with a dash
        r'(?:[a-z' + ul + '-]{2,63}'         # domain label
        r'|xn--[a-z0-9]{1,59})'              # or punycode label
        r'(?<!-)'                            # can't end with a dash
        r'\.?'                               # may have a trailing dot
    )
    host_re = '(' + hostname_re + domain_re + tld_re + '|localhost)'

    netloc_re = r'(?:' + ipv4_re + '|' + ipv6_re + '|' + host_re + ')' + r'(?::\d{2,5})?'
    return netloc_re
