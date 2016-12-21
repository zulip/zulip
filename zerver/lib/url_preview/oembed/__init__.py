from __future__ import absolute_import
from typing import Optional, Any, Text
from pyoembed import oEmbed, PyOembedException


def get_oembed_data(url, maxwidth=640, maxheight=480):
    # type: (Text, Optional[int], Optional[int]) -> Any
    try:
        data = oEmbed(url, maxwidth=maxwidth, maxheight=maxheight)
    except PyOembedException:
        return None

    data['image'] = data.get('thumbnail_url')
    return data
