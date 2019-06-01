from bs4 import BeautifulSoup, SoupStrainer
from typing import Optional, Dict, Any
from pyoembed import oEmbed, PyOembedException

def get_oembed_data(url: str,
                    maxwidth: Optional[int]=640,
                    maxheight: Optional[int]=480) -> Optional[Dict[str, Any]]:
    try:
        data = oEmbed(url, maxwidth=maxwidth, maxheight=maxheight)
    except PyOembedException:
        return None

    oembed_resource_type = data.get('type', '')
    image = data.get('url', data.get('image'))
    thumbnail = data.get('thumbnail_url')
    html = data.pop('html', '')
    if oembed_resource_type == 'photo' and image:
        data['image'] = image
        # Add a key to identify oembed metadata as opposed to other metadata
        data['oembed'] = True

    elif oembed_resource_type == 'video' and html and thumbnail:
        data['html'] = get_safe_html(html)
        data['image'] = thumbnail
        # Add a key to identify oembed metadata as opposed to other metadata
        data['oembed'] = True

    return data

def get_safe_html(html: str) -> str:
    """Return a safe version of the oEmbed html.

    Verify that the HTML:
    1. has a single iframe
    2. the src uses a schema relative URL or explicitly specifies http(s)

    """
    if html.startswith('<![CDATA[') and html.endswith(']]>'):
        html = html[9:-3]
    soup = BeautifulSoup(html, 'lxml', parse_only=SoupStrainer('iframe'))
    iframe = soup.find('iframe')
    if iframe is not None and iframe.get('src').startswith(('http://', 'https://', '//')):
        return str(soup)
    return ''
