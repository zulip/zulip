# For documentation on Sphinx configuration options, see:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
# https://myst-parser.readthedocs.io/en/latest/sphinx/reference.html
# https://sphinx-rtd-theme.readthedocs.io/en/stable/configuring.html
# https://sphinx-design.readthedocs.io/en/latest/tabs.html

import os
import sys
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from version import LATEST_RELEASE_VERSION, ZULIP_VERSION

on_rtd = os.environ.get("READTHEDOCS") == "True"

# General configuration

extensions = [
    "myst_parser",
    "sphinx_rtd_theme",
    "sphinx_design",
]
templates_path = ["_templates"]
project = "Zulip"
copyright = "2012–2015 Dropbox, Inc., 2015–2021 Kandra Labs, Inc., and contributors"
author = "The Zulip Team"
version = ZULIP_VERSION
release = ZULIP_VERSION
exclude_patterns = ["_build", "README.md"]
suppress_warnings = [
    "myst.header",
]
pygments_style = "sphinx"

# Options for Markdown parser

myst_enable_extensions = [
    "colon_fence",
    "substitution",
]
myst_heading_anchors = 6
myst_substitutions = {
    "LATEST_RELEASE_VERSION": LATEST_RELEASE_VERSION,
}

# Options for HTML output

html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "collapse_navigation": not on_rtd,  # makes local builds much faster
    "logo_only": True,
}
html_logo = "images/zulip-logo.svg"
html_static_path = ["_static"]


def setup(app: Any) -> None:
    # overrides for wide tables in RTD theme
    app.add_css_file("theme_overrides.css")  # path relative to _static
