import os

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../")


def markdown_panel(request: HttpRequest) -> HttpResponse:
    context = {
        # We set isolated_page to avoid clutter from footer/header.
        "isolated_page": True,
    }
    return render(request, "zerver/markdown_panel.html", context)
