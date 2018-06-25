import re
import urllib

from typing import Optional
from xml.etree.cElementTree import Element, SubElement
from zerver.lib.bugdown import arguments

def rewrite_local_links_to_relative(link: str) -> str:
    """ If the link points to a local destination we can just switch to that
    instead of opening a new tab. """

    if arguments.db_data:
        realm_uri_prefix = arguments.db_data['realm_uri'] + "/"
        if link.startswith(realm_uri_prefix):
            # +1 to skip the `/` before the hash link.
            return link[len(realm_uri_prefix):]

    return link

upload_title_re = re.compile("^(https?://[^/]*)?(/user_uploads/\\d+)(/[^/]*)?/[^/]*/(?P<filename>[^/]*)$")
def url_filename(url: str) -> str:
    """Extract the filename if a URL is an uploaded file, or return the original URL"""
    match = upload_title_re.match(url)
    if match:
        return match.group('filename')
    else:
        return url

def sanitize_url(url: str) -> Optional[str]:
    """
    Sanitize a url against xss attacks.
    See the docstring on markdown.inlinepatterns.LinkPattern.sanitize_url.
    """
    try:
        parts = urllib.parse.urlparse(url.replace(' ', '%20'))
        scheme, netloc, path, params, query, fragment = parts
    except ValueError:
        # Bad url - so bad it couldn't be parsed.
        return ''

    # If there is no scheme or netloc and there is a '@' in the path,
    # treat it as a mailto: and set the appropriate scheme
    if scheme == '' and netloc == '' and '@' in path:
        scheme = 'mailto'
    elif scheme == '' and netloc == '' and len(path) > 0 and path[0] == '/':
        # Allow domain-relative links
        return urllib.parse.urlunparse(('', '', path, params, query, fragment))
    elif (scheme, netloc, path, params, query) == ('', '', '', '', '') and len(fragment) > 0:
        # Allow fragment links
        return urllib.parse.urlunparse(('', '', '', '', '', fragment))

    # Zulip modification: If scheme is not specified, assume http://
    # We re-enter sanitize_url because netloc etc. need to be re-parsed.
    if not scheme:
        return sanitize_url('http://' + url)

    locless_schemes = ['mailto', 'news', 'file', 'bitcoin']
    if netloc == '' and scheme not in locless_schemes:
        # This fails regardless of anything else.
        # Return immediately to save additional processing
        return None

    # Upstream code will accept a URL like javascript://foo because it
    # appears to have a netloc.  Additionally there are plenty of other
    # schemes that do weird things like launch external programs.  To be
    # on the safe side, we whitelist the scheme.
    if scheme not in ('http', 'https', 'ftp', 'mailto', 'file', 'bitcoin'):
        return None

    # Upstream code scans path, parameters, and query for colon characters
    # because
    #
    #    some aliases [for javascript:] will appear to urllib.parse to have
    #    no scheme. On top of that relative links (i.e.: "foo/bar.html")
    #    have no scheme.
    #
    # We already converted an empty scheme to http:// above, so we skip
    # the colon check, which would also forbid a lot of legitimate URLs.

    # Url passes all tests. Return url as-is.
    return urllib.parse.urlunparse((scheme, netloc, path, params, query, fragment))
