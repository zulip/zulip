import logging
import os
import subprocess

from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def silhouette_svg(request: HttpRequest, seed: str, size: int = 80) -> HttpResponse:
    size = max(16, min(512, int(size)))
    # Resolve tool path at runtime
    tool_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "tools",
        "silhouette_generate.js",
    )

    try:
        proc = subprocess.run(
            ["node", tool_path, seed, str(size)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, "node", stderr=proc.stderr)

        svg = proc.stdout

    except Exception as e:
        logger.error("silhouette_svg error: %s: %s", type(e).__name__, e)
        # fallback simple SVG with generic color
        color = f"#{abs(hash(seed)) & 0xFFFFFF:06x}"
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"><rect width="100%" height="100%" fill="{color}"/></svg>'

    return HttpResponse(svg, content_type="image/svg+xml")
