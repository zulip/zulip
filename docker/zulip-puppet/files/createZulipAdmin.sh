#!/bin/bash

if [ ! -z "$ZULIP_USER_CREATION_ENABLED" ] && ([ -z "$ZULIP_USER_DOMAIN" ] || [ -z "$ZULIP_USER_EMAIL" ]); then
    echo "No zulip user configuration given."
    exit 100
fi
# Doing everything in python, even I never coded in python #YOLO
/home/zulip/deployments/current/manage.py shell <<EOF
from django.core.management.base import CommandError
from zerver.lib.create_user import create_user
from zerver.lib.actions import do_change_is_admin
from zerver.models import Realm, get_realm, email_to_username
from zerver.decorator import get_user_profile_by_email

try:
    realm = get_realm('$ZULIP_USER_DOMAIN')
except Realm.DoesNotExist:
    raise CommandError("Realm/Domain does not exist.")

try:
    create_user('$ZULIP_USER_EMAIL', '$ZULIP_USER_PASS', realm, '$ZULIP_USER_FULLNAME', email_to_username('$ZULIP_USER_EMAIL'))
except:
    pass

User = get_user_profile_by_email(email='$ZULIP_USER_EMAIL')
do_change_is_admin(User, True, 'administer')
User.save()
quit()
EOF
exit 200
