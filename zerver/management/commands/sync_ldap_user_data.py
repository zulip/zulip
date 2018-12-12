import logging
import ldap
import tempfile
from typing import Any
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from zerver.lib.logging_util import log_to_file
from zerver.models import UserProfile
from zerver.lib.actions import do_create_user
from zerver.lib.actions import do_activate_user, do_reactivate_user, do_deactivate_user
from zerver.lib.actions import do_change_avatar_fields
from zerver.lib.upload import upload_avatar_image
from zerver.models import get_user
from zerver.models import UserProfile, Realm, get_user_profile_by_id, \
remote_user_to_email, email_to_username, get_realm
from zproject.backends import ZulipLDAPUserPopulator, ZulipLDAPException


## Setup ##
logger = logging.getLogger(__name__)
log_to_file(logger, settings.LDAP_SYNC_LOG_PATH)

# update users avatar
def set_avatar(user: UserProfile, filename: str) -> None:
     upload_avatar_image(open(filename, 'rb'), user, user)
     do_change_avatar_fields(user, UserProfile.AVATAR_FROM_USER)

# Run this on a cronjob to pick up on name changes.
def sync_ldap_user_data() -> None:
    logger.info("Starting update.")
    backend = ZulipLDAPUserPopulator()

    # next code will pre-create users stored on an external LDAP directory
    # and update their avatar and status
    realm = get_realm("")
    try:
      l = ldap.initialize(settings.AUTH_LDAP_SERVER_URI)
      l.simple_bind_s(settings.AUTH_LDAP_BIND_DN,settings.AUTH_LDAP_BIND_PASSWORD)
    except ldap.LDAPError as e:
      print(e)
    base_dn = settings.AUTH_LDAP_USER_SEARCH.base_dn
    search_scope = settings.AUTH_LDAP_USER_SEARCH.scope
    retrieve_attributes = ['cn','uid','displayName','mail','userAccountControl','memberOf', 'thumbnailPhoto']
    search_filter = '(mail=*)'
    try:
      ldap_result_id = l.search(base_dn, search_scope, search_filter, retrieve_attributes)
      result_set = []
      while 1:
        result_type, result_data = l.result(ldap_result_id, 0)
        if (result_data == []):
            break
        else:
            if result_type == ldap.RES_SEARCH_ENTRY:
                email = result_data[0][1]['mail'][0].decode("utf-8")
                name = result_data[0][1]['displayName'][0].decode('utf-8')
                member_of = result_data[0][1]['memberOf']
                disabled = bool(int(result_data[0][1]['userAccountControl'][0].decode("utf-8")) & 2)
                u = get_user(email, realm)
                if not UserProfile.objects.filter(delivery_email__iexact=email).exists():
                  u = do_create_user(email, None, realm, name, name)
                  logger.info("Create %s" % (email))
                if disabled and u.is_active:
                  do_deactivate_user(u)
                  logger.info("Deactivate %s" % (email))
                elif not disabled and not u.is_active:
                  do_reactivate_user(u)
                  logger.info("Reactivate %s" % (email))
                try:
                  if u.avatar_source == UserProfile.AVATAR_FROM_GRAVATAR:
                    with tempfile.NamedTemporaryFile() as temp:
                      temp.seek(0)
                      temp.write(result_data[0][1]['thumbnailPhoto'][0])
                      temp.flush()
                      set_avatar(u,temp.name)
                      logger.info("Updated %s avatar" % (email))
                except:
                  pass

    except ldap.LDAPError as e:
      print(e)
    l.unbind_s()

    for u in UserProfile.objects.select_related().filter(is_active=True, is_bot=False).all():
        # This will save the user if relevant, and will do nothing if the user
        # does not exist.
        try:
            if backend.populate_user(backend.django_to_ldap_username(u.email)) is not None:
                logger.info("Updated %s." % (u.email,))
            else:
                logger.warning("Did not find %s in LDAP." % (u.email,))
        except ZulipLDAPException as e:
            logger.error("Error attempting to update user %s:" % (u.email,))
            logger.error(e)
    logger.info("Finished update.")

class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> None:
        sync_ldap_user_data()
