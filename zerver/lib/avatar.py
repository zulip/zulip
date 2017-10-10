from django.conf import settings

if False:
    from zerver.models import UserProfile

from typing import Any, Dict, Optional, Text

from zerver.lib.avatar_hash import gravatar_hash, user_avatar_path_from_ids
from zerver.lib.upload import upload_backend, MEDIUM_AVATAR_SIZE
from zerver.models import UserProfile
from six.moves import urllib

def avatar_url(user_profile, medium=False, client_gravatar=False):
    # type: (UserProfile, bool, bool) -> Text

    return get_avatar_field(
        user_id=user_profile.id,
        realm_id=user_profile.realm_id,
        email=user_profile.email,
        avatar_source=user_profile.avatar_source,
        avatar_version=user_profile.avatar_version,
        medium=medium,
        client_gravatar=client_gravatar,
    )

def avatar_url_from_dict(userdict, medium=False):
    # type: (Dict[str, Any], bool) -> Text
    '''
    DEPRECATED: We should start using
                get_avatar_field to populate users,
                particulary for codepaths where the
                client can compute gravatar URLS
                on the client side.
    '''
    url = _get_unversioned_avatar_url(
        userdict['id'],
        userdict['avatar_source'],
        userdict['realm_id'],
        email=userdict['email'],
        medium=medium)
    url += '&version=%d' % (userdict['avatar_version'],)
    return url

def get_avatar_field(user_id,
                     realm_id,
                     email,
                     avatar_source,
                     avatar_version,
                     medium,
                     client_gravatar):
    # type: (int, int, Text, Text, int, bool, bool) -> Optional[Text]
    '''
    Most of the parameters to this function map to fields
    by the same name in UserProfile (avatar_source, realm_id,
    email, etc.).

    Then there are these:

        medium - This means we want a medium-sized avatar. This can
            affect the "s" parameter for gravatar avatars, or it
            can give us something like foo-medium.png for
            user-uploaded avatars.

        client_gravatar - If the client can compute their own
            gravatars, this will be set to True, and we'll avoid
            computing them on the server (mostly to save bandwidth).
    '''

    if client_gravatar:
        '''
        If our client knows how to calculate gravatar hashes, we
        will return None and let the client compute the gravatar
        url.
        '''
        if settings.ENABLE_GRAVATAR:
            if avatar_source == UserProfile.AVATAR_FROM_GRAVATAR:
                return None

    '''
    If we get this far, we'll compute an avatar URL that may be
    either user-uploaded or a gravatar, and then we'll add version
    info to try to avoid stale caches.
    '''
    url = _get_unversioned_avatar_url(
        user_profile_id=user_id,
        avatar_source=avatar_source,
        realm_id=realm_id,
        email=email,
        medium=medium,
    )
    url += '&version=%d' % (avatar_version,)
    return url

def get_gravatar_url(email, avatar_version, medium=False):
    # type: (Text, int, bool) -> Text
    url = _get_unversioned_gravatar_url(email, medium)
    url += '&version=%d' % (avatar_version,)
    return url

def _get_unversioned_gravatar_url(email, medium):
    # type: (Text, bool) -> Text
    if settings.ENABLE_GRAVATAR:
        gravitar_query_suffix = "&s=%s" % (MEDIUM_AVATAR_SIZE,) if medium else ""
        hash_key = gravatar_hash(email)
        return u"https://secure.gravatar.com/avatar/%s?d=identicon%s" % (hash_key, gravitar_query_suffix)
    return settings.DEFAULT_AVATAR_URI+'?x=x'

def _get_unversioned_avatar_url(user_profile_id, avatar_source, realm_id, email=None, medium=False):
    # type: (int, Text, int, Optional[Text], bool) -> Text
    if avatar_source == u'U':
        hash_key = user_avatar_path_from_ids(user_profile_id, realm_id)
        return upload_backend.get_avatar_url(hash_key, medium=medium)
    assert email is not None
    return _get_unversioned_gravatar_url(email, medium)

def absolute_avatar_url(user_profile):
    # type: (UserProfile) -> Text
    """Absolute URLs are used to simplify logic for applications that
    won't be served by browsers, such as rendering GCM notifications."""
    return urllib.parse.urljoin(user_profile.realm.uri, avatar_url(user_profile))
