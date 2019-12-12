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
        data['html'] = strip_cdata(html)
        data['image'] = thumbnail
        # Add a key to identify oembed metadata as opposed to other metadata
        data['oembed'] = True

    return data

def strip_cdata(html: str) -> str:
    # Work around a bug in SoundCloud's XML generation:
    # <html>&lt;![CDATA[&lt;iframe ...&gt;&lt;/iframe&gt;]]&gt;</html>
    if html.startswith('<![CDATA[') and html.endswith(']]>'):
        html = html[9:-3]
    return html
