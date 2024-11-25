import os

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

background_colors = [
    {"name": "Default background", "css_var": "--color-background"},
    {"name": "Popover background", "css_var": "--color-background-popover-menu"},
    {"name": "Modal background", "css_var": "--color-background-modal"},
    {"name": "Compose background", "css_var": "--color-compose-box-background"},
]


def get_svg_filenames() -> list[str]:
    icons_dir = os.path.join(os.path.dirname(__file__), "../../../web/shared/icons")

    # Get all .svg file names from the directory
    svg_files = [f for f in os.listdir(icons_dir) if f.endswith(".svg")]

    # Remove the .svg extension from the file names
    icon_names = [os.path.splitext(f)[0] for f in svg_files]

    # Sort the list alphabetically
    return sorted(icon_names)


def dev_buttons_design_testing(request: HttpRequest) -> HttpResponse:
    context = {
        "background_colors": background_colors,
        "icons": get_svg_filenames(),
        # We set isolated_page to avoid clutter from footer/header.
        "isolated_page": True,
    }
    return render(request, "zerver/development/design_testing/buttons.html", context)
