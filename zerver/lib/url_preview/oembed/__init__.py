from typing import Optional, Dict, Any
from pyoembed import oEmbed, PyOembedException


def get_oembed_data(url: str,
                    maxwidth: Optional[int]=640,
                    maxheight: Optional[int]=480) -> Optional[Dict[str, Any]]:
    try:
        data = oEmbed(url, maxwidth=maxwidth, maxheight=maxheight)
    except PyOembedException:
        return None

    data['image'] = data.get('thumbnail_url')
    type_ = data.get('type', '')
    image = data.get('url', data.get('image'))
    if type_ == 'photo' and image:
        # Add a key to identify oembed metadata as opposed to other metadata
        data['oembed'] = True

    return data
