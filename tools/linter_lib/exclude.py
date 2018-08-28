# Exclude some directories and files from lint checking
EXCLUDED_FILES = [
    # Third-party code that doesn't match our style
    "puppet/apt/.forge-release",
    "puppet/apt/README.md",
    "puppet/apt/manifests/backports.pp",
    "puppet/apt/manifests/params.pp",
    "puppet/apt/manifests/release.pp",
    "puppet/apt/manifests/unattended_upgrades.pp",
    "puppet/stdlib/tests/file_line.pp",
    "static/third",
    # Transifex syncs translation.json files without trailing
    # newlines; there's nothing other than trailing newlines we'd be
    # checking for in these anyway.
    "static/locale",
]

PUPPET_CHECK_RULES_TO_EXCLUDE = [
    "--no-documentation-check",
    "--no-80chars-check",
]
