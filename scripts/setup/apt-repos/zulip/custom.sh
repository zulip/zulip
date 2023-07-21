#!/usr/bin/env bash
set -euo pipefail

if [[ ! -e /usr/share/doc/groonga-apt-source/copyright ]]; then
    arrow_keyring=$(readlink -f "$LIST_PATH/apache-arrow-keyring.gpg")
    pgroonga_apt_sign_key=$(readlink -f "$LIST_PATH/pgroonga-packages.groonga.org.asc")

    remove_pgroonga_apt_tmp_dir() {
        rm -rf "$pgroonga_apt_tmp_dir"
    }
    pgroonga_apt_tmp_dir=$(mktemp --directory)
    trap remove_pgroonga_apt_tmp_dir EXIT

    {
        cd "$pgroonga_apt_tmp_dir" || exit 1
        tmp_gpg_home=.gnupg
        gpg --homedir="$tmp_gpg_home" --import "$pgroonga_apt_sign_key"
        # Find fingerprint of the first key.
        pgroonga_apt_sign_key_fingerprint=$(
            gpg --homedir="$tmp_gpg_home" --with-colons --list-keys \
                | grep '^fpr:' \
                | cut --delimiter=: --fields=10 \
                | head --lines=1
        )
        os_info="$(. /etc/os-release && printf '%s\n' "$ID" "$VERSION_CODENAME")"
        {
            read -r distribution
            read -r release
        } <<<"$os_info"

        if [ "$distribution" = debian ] && [ "$release" = bookworm ]; then
            # As of Debian 12, the Groonga repository depends on the
            # Apache Arrow repository.
            arrow_apt_source_deb="apache-arrow-apt-source-latest-$release.deb"
            arrow_apt_source_deb_sign="$arrow_apt_source_deb.asc"
            curl -fLO --retry 3 "https://apache.jfrog.io/artifactory/arrow/$distribution/$arrow_apt_source_deb"
            curl -fLO --retry 3 "https://apache.jfrog.io/artifactory/arrow/$distribution/$arrow_apt_source_deb_sign"
            gpgv --keyring="$arrow_keyring" "$arrow_apt_source_deb_sign" "$arrow_apt_source_deb"
        fi

        groonga_apt_source_deb="groonga-apt-source-latest-$release.deb"
        groonga_apt_source_deb_sign="$groonga_apt_source_deb.asc.$pgroonga_apt_sign_key_fingerprint"
        curl -fLO --retry 3 "https://packages.groonga.org/$distribution/$groonga_apt_source_deb"
        curl -fLO --retry 3 "https://packages.groonga.org/$distribution/$groonga_apt_source_deb_sign"
        gpg \
            --homedir="$tmp_gpg_home" \
            --verify \
            "$groonga_apt_source_deb_sign" \
            "$groonga_apt_source_deb"
        # To suppress the following warning by "apt-get install":
        #   N: Download is performed unsandboxed as root as file
        #   '.../groonga-apt-source-latest-$release.deb' couldn't be
        #   accessed by user '_apt'. - pkgAcquire::Run (13: Permission denied)
        chown _apt .

        if [ "$distribution" = debian ] && [ "$release" = bookworm ]; then
            apt-get -y install "./$arrow_apt_source_deb"
        fi
        apt-get -y install "./$groonga_apt_source_deb"
    }
    touch "$STAMP_FILE"
fi
