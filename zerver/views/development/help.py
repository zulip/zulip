import os

import werkzeug
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def help_dev_mode_view(request: HttpRequest, subpath: str = "") -> HttpResponse:
    """
    Dev only view that displays help information for setting up the
    help center dev server in the default `run-dev` mode where the
    help center server is not running. Also serves raw MDX content when
    `raw` query param is passed is passed.
    """

    def read_mdx_file(filename: str) -> HttpResponse:
        file_path = os.path.join(
            settings.DEPLOY_ROOT, "starlight_help", "src", "content", "docs", f"{filename}.mdx"
        )
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            return HttpResponse(content, content_type="text/plain")
        except OSError:
            return HttpResponse("Error reading MDX file", status=500)

    mdx_file_exists = False
    is_requesting_raw_file = request.GET.get("raw") == ""

    if subpath:
        subpath = werkzeug.utils.secure_filename(subpath)
        raw_url = f"/help/{subpath}?raw"
        mdx_path = os.path.join(
            settings.DEPLOY_ROOT, "starlight_help", "src", "content", "docs", f"{subpath}.mdx"
        )
        mdx_file_exists = os.path.exists(mdx_path) and "/include/" not in mdx_path
        if mdx_file_exists and is_requesting_raw_file:
            return read_mdx_file(subpath)
    else:
        if request.path.endswith("/"):
            raw_url = "/help/?raw"
        else:
            raw_url = "/help?raw"
        mdx_file_exists = True
        if is_requesting_raw_file:
            return read_mdx_file("index")

    return render(
        request,
        "zerver/development/dev_help.html",
        {
            "subpath": subpath,
            "mdx_file_exists": mdx_file_exists,
            "raw_url": raw_url,
        },
    )
