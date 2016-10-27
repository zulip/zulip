from __future__ import absolute_import
from typing import Optional, Any
from six import text_type
from pyoembed import oEmbed, PyOembedException


def get_oembed_data(url, maxwidth=640, maxheight=480):
    # type: (text_type, Optional[int], Optional[int]) -> Any
    try:
        data = oEmbed(url, maxwidth=maxwidth, maxheight=maxheight)
    except PyOembedException:
        return None

    data['image'] = data.get('thumbnail_url')
    return data
