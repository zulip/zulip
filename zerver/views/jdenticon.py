import logging
import os
import subprocess

from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def jdenticon_svg(request: HttpRequest, seed: str, size: int = 80) -> HttpResponse:
    size = max(16, min(512, int(size)))

    # Resolve tool path dynamically
    tool_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "tools",
        "jdenticon_generate.js",
    )

    try:
        # Try generating with Node
        proc = subprocess.run(
            ["node", tool_path, seed, str(size)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if proc.returncode != 0:
            logger.error("jdenticon subprocess failed: %s", proc.stderr)
            raise subprocess.CalledProcessError(proc.returncode, "node", stderr=proc.stderr)

        svg = proc.stdout

    except Exception as e:
        logger.error("jdenticon_svg error: %s: %s", type(e).__name__, e)
        # fallback simple SVG
        color = f"#{abs(hash(seed)) & 0xFFFFFF:06x}"
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{size}" height="{size}">'
            f'<rect width="100%" height="100%" fill="{color}"/></svg>'
        )

    return HttpResponse(svg, content_type="image/svg+xml")
