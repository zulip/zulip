#!/usr/bin/env bash

set -e
set -u

if ! grep -Eq 'SENTRY_DSN|SENTRY_FRONTEND_DSN' /etc/zulip/settings.py; then
    echo "sentry: No DSN configured!  Set SENTRY_DSN or SENTRY_FRONTEND_DSN in /etc/zulip/settings.py"
    exit 0
fi

if ! SENTRY_AUTH_TOKEN=$(crudini --get /etc/zulip/zulip-secrets.conf secrets sentry_release_auth_token); then
    echo "sentry: No release auth token set!  Set sentry_release_auth_token in /etc/zulip/zulip-secrets.conf"
    exit 0
fi
export SENTRY_AUTH_TOKEN

# shellcheck disable=SC2034
if ! sentry_org=$(crudini --get /etc/zulip/zulip.conf sentry organization); then
    echo "sentry: No organization set!  Set sentry.organization in /etc/zulip/zulip.conf"
    exit 0
fi

sentry_project=$(crudini --get /etc/zulip/zulip.conf sentry project)
sentry_frontend_project=$(crudini --get /etc/zulip/zulip.conf sentry frontend_project)
if [ -z "$sentry_project" ] && [ -z "$sentry_frontend_project" ]; then
    echo "sentry: No project set!  Set sentry.project and/or sentry.frontend_project in /etc/zulip/zulip.conf"
    exit 0
fi

if [ -n "$sentry_project" ] && ! grep -q 'SENTRY_DSN' /etc/zulip/settings.py; then
    echo "sentry: sentry.project is set but SENTRY_DSN is not set in /etc/zulip/settings.py"
    exit 0
fi
if [ -n "$sentry_frontend_project" ] && ! grep -q 'SENTRY_FRONTEND_DSN' /etc/zulip/settings.py; then
    echo "sentry: sentry.frontend_project is set but SENTRY_FRONTEND_DSN is not set in /etc/zulip/settings.py"
    exit 0
fi

if ! which sentry-cli >/dev/null; then
    echo "sentry: No sentry-cli installed!"
    exit 0
fi

# shellcheck disable=SC2034
sentry_release="zulip-server@$ZULIP_NEW_VERSION"
