# Exclude some directories and files from lint checking
EXCLUDED_FILES = [
    # Third-party code that doesn't match our style
    "puppet/apt/.forge-release",
    "puppet/apt/README.md",
    "static/third",
    # Transifex syncs translation.json files without trailing
    # newlines; there's nothing other than trailing newlines we'd be
    # checking for in these anyway.
    "static/locale",
]
