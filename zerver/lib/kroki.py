from typing import Optional

import requests
from django.conf import settings


def render_kroki(text: str, diagram_type: str) -> Optional[str]:
    """Render diagrams from textual descriptions

    Returns the HTML string, or None in cases like there was some
    syntax error or diagram type was not correct.

    Keyword arguments:
    text -- Text string with the Kroki diagram to render.
            Don't split text into paragraphs as they often
            contain information which links each other.

    diagram_type -- Text string required when making the POST request.
                    This indicates the diagram type we want for the
                    given input source.
    """

    if not settings.KROKI_SERVER_URL:
        return None

    data = dict(
        diagram_source=text,
        diagram_type=diagram_type,
        output_format="SVG",
    )

    try:
        response = requests.post(url=settings.KROKI_SERVER_URL, json=data, timeout=10)
    except requests.exceptions.RequestException:
        return None

    if not response.ok:
        return None

    return response.text
