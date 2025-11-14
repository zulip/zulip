import subprocess
import os
import logging
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from django.conf import settings
from pathlib import Path

logger = logging.getLogger(__name__)

@require_GET
def jdenticon_svg(request, seed: str, size: int = 80):
    size = max(16, min(512, int(size)))
    # Resolve tool path at runtime, not at import time
    tool_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "tools", "jdenticon_generate.js")
    
    print(f"DEBUG: jdenticon_svg called with seed={seed}, size={size}")
    print(f"DEBUG: tool_path={tool_path}")
    print(f"DEBUG: Tool exists: {os.path.exists(tool_path)}")
    
    try:
        # Try to run node directly first to check if it works
        result = subprocess.run(
            ["node", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        print(f"DEBUG: Node version check: {result.stdout.strip()}")
        
        # Now try jdenticon
        proc = subprocess.run(
            ["node", tool_path, seed, str(size)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        
        if proc.returncode != 0:
            print(f"DEBUG: subprocess returned code {proc.returncode}")
            print(f"DEBUG: stderr: {proc.stderr}")
            raise subprocess.CalledProcessError(proc.returncode, "node", stderr=proc.stderr)
        
        svg = proc.stdout
        print(f"DEBUG: SVG generated successfully, length={len(svg)}")
        
    except subprocess.CalledProcessError as e:
        print(f"DEBUG: CalledProcessError: {e.stderr}")
        logger.error(f"jdenticon subprocess failed: {e.stderr}")
        # fallback simple SVG
        color = "#%06x" % (abs(hash(seed)) & 0xFFFFFF)
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"><rect width="100%" height="100%" fill="{color}"/></svg>'
    except Exception as e:
        print(f"DEBUG: Exception: {type(e).__name__}: {e}")
        logger.error(f"jdenticon_svg error: {type(e).__name__}: {e}")
        # fallback simple SVG
        color = "#%06x" % (abs(hash(seed)) & 0xFFFFFF)
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"><rect width="100%" height="100%" fill="{color}"/></svg>'
    
    return HttpResponse(svg, content_type="image/svg+xml")
