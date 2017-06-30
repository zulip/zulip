#!/bin/bash

if ([ "$ZULIP_USER_CREATION_ENABLED" == "True" ] && [ "$ZULIP_USER_CREATION_ENABLED" == "true" ]) && ([ -z "$ZULIP_USER_DOMAIN" ] || [ -z "$ZULIP_USER_EMAIL" ] || [ -z "$ZULIP_USER_FULLNAME" ] || [ -z "$ZULIP_USER_PASS" ]); then
    echo "No zulip user configuration given."
    exit 1
fi
set +e
# Doing everything in python, even I never coded in python #YOLO
sudo -H -u zulip -g zulip bash <<BASH
/home/zulip/deployments/current/manage.py create_realm --string_id="$ZULIP_USER_DOMAIN" --name="$ZULIP_USER_DOMAIN"
/home/zulip/deployments/current/manage.py create_user --this-user-has-accepted-the-tos --realm "$ZULIP_USER_DOMAIN" "$ZULIP_USER_EMAIL" "$ZULIP_USER_FULLNAME"
/usr/bin/expect <<EOF
set timeout 5
spawn /bin/bash
match_max 100000
expect "$ "
send -- "/home/zulip/deployments/current/manage.py changepassword $ZULIP_USER_EMAIL"
expect -exact "/home/zulip/deployments/current/manage.py changepassword $ZULIP_USER_EMAIL"
send -- " \r"
expect "Password: "
send -- "$ZULIP_USER_PASS\r"
expect -exact "\r
Password (again): "
send -- "$ZULIP_USER_PASS\r"
expect "$ "
send -- "exit\r"
expect eof
EOF
/home/zulip/deployments/current/manage.py knight "$ZULIP_USER_EMAIL" -f
BASH
