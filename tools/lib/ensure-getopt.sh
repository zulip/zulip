# shellcheck shell=bash
#
# Usage:
#   . ensure-getopt.sh
#
# Ensures a GNU-based getopt is available in PATH.
# May add to PATH, or exit with a message to stderr.
#
# On any GNU/Linux system this is of course a non-issue.
# (The usual implementation comes from util-linux,
# as a thin CLI wrapper around GNU getopt(3).)
# So this is only relevant for development scripts that
# may be run outside the Zulip server development environment.
#
# On Windows the situation is unknown.  (The GNU coreutils are
# a non-issue: we inevitably require Git, and Git for Windows comes
# with a GNU environment called "Git BASH", based on MSYS2.)
# TODO: Find out if getopt is in the base Git BASH environment,
#   and if not then add support here similar to that for Homebrew.
#
# So this is really all about macOS.  Fortunately it's easy to get
# getopt installed there too... plus, many people already have
# it installed but just not in their PATH.  We write our scripts
# for a GNU environment, so we bring it into the PATH.
#
# See also:
#  * tools/lib/ensure-coreutils.sh in zulip-mobile, which does
#    a similar job for the GNU coreutils.

# Check, silently, for a working getopt on the PATH.
check_getopt() {
    # The BSD-based implementation found on macOS by default
    # doesn't understand --help, and prints " --" for this.
    getopt --help 2>&1 | grep -q -e --version
}

# Either get Homebrew's GNU-based getopt on the PATH, or error out.
try_homebrew_getopt() {
    local homebrew_prefix="$1"

    # Homebrew by default leaves this package/formula out of the PATH.
    local homebrew_gnubin="${homebrew_prefix}"/opt/gnu-getopt/bin
    if ! [ -d "${homebrew_gnubin}" ]; then
        cat >&2 <<EOF
This script requires GNU getopt.

Found Homebrew at:
  ${homebrew_prefix}
but no getopt at:
  ${homebrew_gnubin}

Try installing getopt with:
  brew install gnu-getopt
EOF
        return 2
    fi

    export PATH="${homebrew_gnubin}":"$PATH"
    if ! check_getopt; then
        cat >&2 <<EOF
This script requires GNU getopt.

Found Homebrew installation of getopt at:
  ${homebrew_gnubin}
but it doesn't seem to work.

Please report this in "#development help" on https://chat.zulip.org/
and we'll help debug.
EOF
        return 2
    fi
}

ensure_getopt() {
    # If we already have it, then great.
    check_getopt && return

    # Else try finding a Homebrew install of GNU getopt,
    # and putting that on the PATH.
    homebrew_prefix=$(brew --prefix 2>/dev/null || :)
    if [ -n "${homebrew_prefix}" ]; then
        # Found Homebrew.  Either use that, or if we can't then
        # print an error with Homebrew-specific instructions.
        try_homebrew_getopt "${homebrew_prefix}"
        return
    fi

    cat >&2 <<EOF
This script requires GNU getopt.

Install from upstream:
  https://github.com/util-linux/util-linux
or from your favorite package manager.

If you have any questions, ask in "#development help" on https://chat.zulip.org/
and we'll be happy to help.
EOF
    return 2
}

ensure_getopt || exit
