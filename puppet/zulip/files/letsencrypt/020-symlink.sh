#!/usr/bin/env bash

symlink_with_backup() {
    if [ -e "$2" ]; then
        # If the user is setting up our automatic certbot-management on a
        # system that already has certs for Zulip, use some extra caution
        # to keep the old certs available.
        mv -f --backup=numbered "$2" "$2".setup-certbot || true
    fi
    ln -nsf "$1" "$2"
}

if [ -n "${ZULIP_DOMAIN:-}" ]; then
    CERT_DIR="/etc/letsencrypt/live/$ZULIP_DOMAIN"
    symlink_with_backup "$CERT_DIR/privkey.pem" /etc/ssl/private/zulip.key
    symlink_with_backup "$CERT_DIR/fullchain.pem" /etc/ssl/certs/zulip.combined-chain.crt
fi
