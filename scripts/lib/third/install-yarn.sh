#!/bin/sh
set -e

#####################
# install-yarn.sh was patched to install yarn in a custom directory.
# The following changes were made:
# * yarn_link now just simlinks to /usr/bin
# * yarn_detect_profile was removed
# * Paths were changed to variables declared at the top
# * Most of the non error coloration was removed to not distract during installs.
# #######################

reset="\033[0m"
red="\033[31m"
yellow="\033[33m"
gpg_key=9D41F3C3

ZULIP_ROOT="$1"
YARN_DIR_NAME="zulip-yarn"
YARN_DIR="$ZULIP_ROOT/$YARN_DIR_NAME"
YARN_BIN="$YARN_DIR/bin/yarn"

yarn_get_tarball() {
  printf "Downloading tarball...\n"
  if [ "$1" = '--nightly' ]; then
    url=https://nightly.yarnpkg.com/latest.tar.gz
  elif [ "$1" = '--rc' ]; then
    url=https://yarnpkg.com/latest-rc.tar.gz
  elif [ "$1" = '--version' ]; then
    # Validate that the version matches MAJOR.MINOR.PATCH to avoid garbage-in/garbage-out behavior
    version=$2
    if echo $version | grep -qE "^[[:digit:]]+\.[[:digit:]]+\.[[:digit:]]+$"; then
      url="https://yarnpkg.com/downloads/$version/yarn-v$version.tar.gz"
    else
      printf "$red> Version number must match MAJOR.MINOR.PATCH.$reset\n"
      exit 1;
    fi
  else
    url=https://yarnpkg.com/latest.tar.gz
  fi
  # Get both the tarball and its GPG signature
  tarball_tmp=`mktemp -t yarn.tar.gz.XXXXXXXXXX`
  if curl --fail -L -o "$tarball_tmp#1" "$url{,.asc}"; then
    yarn_verify_integrity $tarball_tmp

    printf "Extracting to $YARN_DIR...\n"
    mkdir "$YARN_DIR_NAME"
    tar zxf $tarball_tmp -C "$YARN_DIR_NAME" --strip 1 # extract tarball
    rm $tarball_tmp*
  else
    printf "$red> Failed to download $url.$reset\n"
    exit 1;
  fi
}

# Verifies the GPG signature of the tarball
yarn_verify_integrity() {
  # Check if GPG is installed
  if [[ -z "$(command -v gpg)" ]]; then
    printf "$yellow> WARNING: GPG is not installed, integrity cannot be verified!$reset\n"
    return
  fi

  if [ "$YARN_GPG" == "no" ]; then
    printf "WARNING: Skipping GPG integrity check!\n"
    return
  fi

  printf "Verifying integrity...\n"
  # Grab the public key if it doesn't already exist
  # Zulip patch: Fix the fact that Yarn has extended this keyring and we should always redownload.
  curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | gpg --import

  if [ ! -f "$1.asc" ]; then
    printf "$red> Could not download GPG signature for this Yarn release. This means the release cannot be verified!$reset\n"
    yarn_verify_or_quit "> Do you really want to continue?"
    return
  fi

  # Actually perform the verification
  if gpg --verify "$1.asc" $1; then
    printf "GPG signature looks good\n"
  else
    printf "$red> GPG signature for this Yarn release is invalid! This is BAD and may mean the release has been tampered with. It is strongly recommended that you report this to the Yarn developers.$reset\n"
    yarn_verify_or_quit "> Do you really want to continue?"
  fi
}

yarn_link() {
  printf "Adding to /usr/bin\n"

  version=`$YARN_BIN --version` || (
    printf "$red> Yarn was installed, but doesn't seem to be working :(.$reset\n"
    exit 1;
  )

  ln -nsf "$YARN_BIN" /usr/bin/yarn

  printf "Successfully installed Yarn $version!\n"
}


yarn_reset() {
  unset -f yarn_install yarn_reset yarn_get_tarball yarn_link yarn_verify_integrity yarn_verify_or_quit
}

yarn_install() {
  printf "Installing Yarn!\n"

  if [ -d "$YARN_DIR" ]; then
    if [ -e "$YARN_BIN" ] ; then
      local latest_url
      local specified_version
      local version_type
      if [ "$1" = '--nightly' ]; then
        latest_url=https://nightly.yarnpkg.com/latest-tar-version
        specified_version=`curl -sS $latest_url`
        version_type='latest'
      elif [ "$1" = '--version' ]; then
        specified_version=$2
        version_type='specified'
      elif [ "$1" = '--rc' ]; then
        latest_url=https://yarnpkg.com/latest-rc-version
        specified_version=`curl -sS $latest_url`
        version_type='rc'
      else
        latest_url=https://yarnpkg.com/latest-version
        specified_version=`curl -sS $latest_url`
        version_type='latest'
      fi
      yarn_version=`$YARN_BIN -V`
      yarn_alt_version=`$YARN_BIN --version`
      if [ "$specified_version" = "$yarn_version" -o "$specified_version" = "$yarn_alt_version" ]; then
        printf "Yarn is already at the $specified_version version.\n"
        exit 0
      else
        rm -rf "$YARN_DIR"
      fi
    else
      printf "$red> $YARN_DIR already exists, possibly from a past Yarn install.$reset\n"
      printf "$red> Remove it (rm -rf $YARN_DIR) and run this script again.$reset\n"
      exit 0
    fi
  fi

  yarn_get_tarball $1 $2
  yarn_link
  yarn_reset
}

yarn_verify_or_quit() {
  read -p "$1 [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]
  then
    printf "$red> Aborting$reset\n"
    exit 1
  fi
}

cd $ZULIP_ROOT
yarn_install $2 $3
