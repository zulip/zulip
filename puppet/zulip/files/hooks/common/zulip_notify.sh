#!/usr/bin/env bash

set -e
set -u

if ! zulip_api_key=$(crudini --get /etc/zulip/zulip-secrets.conf secrets zulip_release_api_key); then
    echo "zulip_notify: No zulip_release_api_key set!  Set zulip_release_api_key in /etc/zulip/zulip-secrets.conf"
    exit 0
fi

if ! zulip_notify_bot_email=$(crudini --get /etc/zulip/zulip.conf zulip_notify bot_email); then
    echo "zulip_notify: No zulip_notify.bot_email set in /etc/zulip/zulip.conf"
    exit 0
fi

if ! zulip_notify_server=$(crudini --get /etc/zulip/zulip.conf zulip_notify server); then
    echo "zulip_notify: No zulip_notify.server set in /etc/zulip/zulip.conf"
    exit 0
fi

if ! zulip_notify_stream=$(crudini --get /etc/zulip/zulip.conf zulip_notify stream); then
    echo "zulip_notify: No zulip_notify.stream set in /etc/zulip/zulip.conf"
    exit 0
fi

from=${ZULIP_OLD_MERGE_BASE_COMMIT:-$ZULIP_OLD_VERSION}
to=${ZULIP_NEW_MERGE_BASE_COMMIT:-$ZULIP_NEW_VERSION}
deploy_environment=$(crudini --get /etc/zulip/zulip.conf machine deploy_type || echo "development")
commit_count=$(git rev-list "${from}..${to}" | wc -l)

echo "zulip_notify: Sending notify of $from .. $to ($commit_count commits) for $deploy_environment to $zulip_notify_server"

zulip_send() {
    ./zulip-py3-venv/bin/zulip-send \
        --site "$zulip_notify_server" \
        --user "$zulip_notify_bot_email" \
        --api-key "$zulip_api_key" \
        --stream "$zulip_notify_stream" \
        --subject "$deploy_environment deploy" \
        --message "$1"
}
