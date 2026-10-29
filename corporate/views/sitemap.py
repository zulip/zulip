import os
import re

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.urls import URLPattern
from lxml import etree

from zerver.lib.integrations import CATEGORIES
from zerver.lib.subdomains import is_subdomain_root_or_alias
from zerver.lib.url_redirects import LANDING_PAGE_REDIRECTS
from zerver.views.documentation import get_visible_integrations_for_category

SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Indexable pages that aren't in corporate.urls.landing_page_urls.
EXTRA_MARKETING_PATHS = ["/", "/jobs/"]

# Landing pages that search engines shouldn't index separately.
EXCLUDED_LANDING_PAGE_PATHS = {
    # Its rel=canonical link points to the root page.
    "/hello/",
    # Marked noindex.
    "/attribution/",
}

DOCUMENTATION_LINK_REGEX = re.compile(r"\]\((/(?:api|policies)/[^)\s]*)\)")


def get_landing_page_paths() -> list[str]:
    # Imported here, since corporate.urls imports this module's view.
    from corporate.urls import landing_page_urls

    redirected_paths = {redirect.old_url for redirect in LANDING_PAGE_REDIRECTS}
    paths = []
    for url_pattern in landing_page_urls:
        assert isinstance(url_pattern, URLPattern)
        if url_pattern.pattern.converters:
            # Pages like /apps/<platform> are variants of another page.
            continue
        path = f"/{url_pattern.pattern}"
        if path not in EXCLUDED_LANDING_PAGE_PATHS and path not in redirected_paths:
            paths.append(path)
    return paths


def get_documentation_sidebar_paths(sidebar_file_paths: list[str]) -> list[str]:
    paths = []
    for sidebar_file_path in sidebar_file_paths:
        with open(sidebar_file_path) as f:
            paths += DOCUMENTATION_LINK_REGEX.findall(f.read())
    return paths


def get_api_documentation_paths() -> list[str]:
    return [
        "/api/",
        *get_documentation_sidebar_paths(
            [
                os.path.join(settings.DEPLOY_ROOT, "api_docs/sidebar_index.md"),
                os.path.join(settings.DEPLOY_ROOT, "api_docs/include/rest-endpoints.md"),
            ]
        ),
    ]


def get_policy_documentation_paths() -> list[str]:
    # Relative policy directories are inside the templates directory;
    # see MarkdownDirectoryView.get_path.
    policies_directory = os.path.join(
        settings.DEPLOY_ROOT, "templates", settings.POLICIES_DIRECTORY
    )
    return get_documentation_sidebar_paths([os.path.join(policies_directory, "sidebar_index.md")])


def get_integration_documentation_paths() -> list[str]:
    return [
        "/integrations/",
        *(f"/integrations/category/{category_slug}" for category_slug in sorted(CATEGORIES)),
        *(
            f"/integrations/{integration.name}"
            for integration in get_visible_integrations_for_category("all")
        ),
    ]


def get_help_center_paths() -> list[str]:
    help_center_source_directory = os.path.join(
        settings.DEPLOY_ROOT, "starlight_help/src/content/docs"
    )
    article_names = sorted(
        file_name.removesuffix(".mdx")
        for file_name in os.listdir(help_center_source_directory)
        if file_name.endswith(".mdx")
    )
    return [
        "/help/",
        *(
            f"/help/{article_name}"
            for article_name in article_names
            if article_name not in ["index", "missing"]
        ),
    ]


def get_sitemap_paths() -> list[str]:
    return [
        *EXTRA_MARKETING_PATHS,
        *get_landing_page_paths(),
        *get_help_center_paths(),
        *get_api_documentation_paths(),
        *get_integration_documentation_paths(),
        *get_policy_documentation_paths(),
    ]


def sitemap_view(request: HttpRequest) -> HttpResponse:
    if not (settings.ROOT_DOMAIN_LANDING_PAGE and is_subdomain_root_or_alias(request)):
        return HttpResponseNotFound()

    urlset = etree.Element(f"{{{SITEMAP_NAMESPACE}}}urlset", nsmap={None: SITEMAP_NAMESPACE})
    for path in get_sitemap_paths():
        url = etree.SubElement(urlset, f"{{{SITEMAP_NAMESPACE}}}url")
        etree.SubElement(url, f"{{{SITEMAP_NAMESPACE}}}loc").text = f"https://zulip.com{path}"
    return HttpResponse(
        etree.tostring(urlset, xml_declaration=True, encoding="UTF-8", pretty_print=True),
        content_type="application/xml",
    )
