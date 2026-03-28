# Exclude some directories and files from lint checking
EXCLUDED_FILES = [
    # Third-party code that doesn't match our style
    "web/third",
    # Generated or third-party files
    "docs/THIRDPARTY",
    "docs/translating",
    "locale",
    "node_modules",
    "pnpm-lock.yaml",
    "var",
    "zerver/management/data/unified_reactions.json",
    # We don't want to lint these
    "tools/setup/emoji/emoji_names.py",
    "fixtures",
]

PUPPET_CHECK_RULES_TO_EXCLUDE = [
    "--no-documentation-check",
    "--no-80chars-check",
]
