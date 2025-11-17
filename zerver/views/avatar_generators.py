import os
import subprocess

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from zerver.lib.stream_color import STREAM_ASSIGNMENT_COLORS


def generate_jdenticon_svg(identifier: str, size: int = 80) -> str:
    """
    Generate a Jdenticon-style SVG avatar using the actual Jdenticon library.
    
    Calls the Node.js script that uses the official Jdenticon library.
    Config: https://jdenticon.com/icon-designer.html?config=86444400014146122850195a
    """
    script_path = os.path.join(settings.DEPLOY_ROOT, "tools", "jdenticon_generate.js")
    try:
        result = subprocess.run(
            ["node", script_path, identifier, str(size)],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        # Fallback to a simple SVG if Node.js fails
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"><rect width="{size}" height="{size}" fill="#ddd"/></svg>'


def generate_silhouette_svg(identifier: str, size: int = 80) -> str:
    """
    Generate a colorful silhouette avatar.
    
    Calls the Node.js script that generates colored silhouettes.
    """
    script_path = os.path.join(settings.DEPLOY_ROOT, "tools", "silhouette_generate.js")
    try:
        result = subprocess.run(
            ["node", script_path, identifier, str(size)],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        # Fallback to a simple SVG if Node.js fails
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"><rect width="{size}" height="{size}" fill="#888"/><text x="50%" y="50%" text-anchor="middle" fill="white" font-size="40">?</text></svg>'


def avatar_jdenticon(
    request: HttpRequest, user_id: int
) -> HttpResponse:
    """Serve a Jdenticon avatar for a user."""
    try:
        size = int(request.GET.get('s', 80))
        # Limit size for performance
        size = min(max(size, 16), 512)
    except (ValueError, TypeError):
        size = 80
    
    # Use user_id as identifier for consistent avatars
    identifier = str(user_id)
    svg_content = generate_jdenticon_svg(identifier, size)
    
    response = HttpResponse(svg_content, content_type='image/svg+xml')
    response['Cache-Control'] = 'public, max-age=86400'  # Cache for 1 day
    return response


def avatar_silhouette(
    request: HttpRequest, user_id: int
) -> HttpResponse:
    """Serve a colorful silhouette avatar for a user."""
    try:
        size = int(request.GET.get('s', 80))
        size = min(max(size, 16), 512)
    except (ValueError, TypeError):
        size = 80
    
    # Use user_id as identifier for consistent silhouettes
    identifier = str(user_id)
    svg_content = generate_silhouette_svg(identifier, size)
    
    response = HttpResponse(svg_content, content_type='image/svg+xml')
    response['Cache-Control'] = 'public, max-age=86400'
    return response


def realm_icon_jdenticon(
    request: HttpRequest, realm_id: int
) -> HttpResponse:
    """Serve a Jdenticon icon for a realm/organization."""
    try:
        size = int(request.GET.get('s', 100))
        size = min(max(size, 16), 512)
    except (ValueError, TypeError):
        size = 100
    
    # Use realm_id as identifier
    identifier = f"realm-{realm_id}"
    svg_content = generate_jdenticon_svg(identifier, size)
    
    response = HttpResponse(svg_content, content_type='image/svg+xml')
    response['Cache-Control'] = 'public, max-age=86400'
    return response
