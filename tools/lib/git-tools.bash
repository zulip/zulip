# shellcheck shell=bash

# Borrowed from Git's git-sh-setup.
#
# See git.git commit 92c62a3f4 (from 2010!); as of 2020 with Git 2.26,
# this function has only needed one edit since then, adding localization
# with gettext, which we can omit.
require_clean_work_tree() {
    local action="$1"

    git rev-parse --verify HEAD >/dev/null || exit 1
    git update-index -q --ignore-submodules --refresh
    local err=0

    if ! git diff-files --quiet --ignore-submodules; then
        echo >&2 "Cannot $action: You have unstaged changes."
        err=1
    fi

    if ! git diff-index --cached --quiet --ignore-submodules HEAD --; then
        if [ $err = 0 ]; then
            echo >&2 "Cannot $action: Your index contains uncommitted changes."
        else
            echo >&2 "Additionally, your index contains uncommitted changes."
        fi
        err=1
    fi

    if [ $err = 1 ]; then
        git status --short
        echo >&2 "Doing nothing to avoid losing your work."
        exit 1
    fi
}
