#!/bin/bash -e

# Remove .pyc files to prevent loading stale code.
#
# You can run it automatically on checkout:
#
#     echo ./tools/clean-repo > .git/hooks/post-checkout
#     chmod +x .git/hooks/post-checkout

cd "$(dirname "$0")/.."
find . -name '*.pyc' -print -delete | sed 's|^|[clean-repo] Deleting |'
