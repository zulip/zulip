# See http://zulip.readthedocs.io/en/latest/events-system.html for
# high-level documentation on how this system works.
from __future__ import absolute_import
from __future__ import print_function

import copy
import six
import ujson

from django.utils.translation import ugettext as _
from django.conf import settings
from importlib import import_module
from six.moves import filter, map
from typing import (
    cast, Any, Dict, Iterable, List, Optional, Sequence, Set, Text, Tuple, Union
)

session_engine = import_module(settings.SESSION_ENGINE)

from zerver.lib.alert_words import user_alert_words
from zerver.lib.attachments import user_attachments
from zerver.lib.avatar import avatar_url, avatar_url_from_dict
from zerver.lib.hotspots import get_next_hotspots
from zerver.lib.message import (
    apply_unread_message_event,
    get_unread_message_ids_per_recipient,
)
from zerver.lib.narrow import check_supported_events_narrow_filter
from zerver.lib.soft_deactivation import maybe_catch_up_soft_deactivated_user
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.request import JsonableError
from zerver.lib.topic_mutes import get_topic_mutes
from zerver.lib.actions import (
    validate_user_access_to_subscribers_helper,
    do_get_streams, get_default_streams_for_realm,
    gather_subscriptions_helper, get_cross_realm_dicts,
    get_status_dict, streams_to_dicts_sorted
)
from zerver.lib.upload import get_total_uploads_size_for_user
from zerver.tornado.event_queue import request_event_queue, get_user_events
from zerver.models import Client, Message, Realm, UserPresence, UserProfile, \
    get_user_profile_by_id, \
    get_active_user_dicts_in_realm, realm_filters_for_realm, get_user,\
    get_owned_bot_dicts, custom_profile_fields_for_realm, get_realm_domains
from zproject.backends import password_auth_enabled
from version import ZULIP_VERSION


def get_realm_user_dicts(user_profile):
    # type: (UserProfile) -> List[Dict[str, Text]]
    return [{'email': userdict['email'],
             'user_id': userdict['id'],
             'avatar_url': avatar_url_from_dict(userdict),
             'is_admin': userdict['is_realm_admin'],
             'is_bot': userdict['is_bot'],
             'full_name': userdict['full_name'],
             'timezone': userdict['timezone']}
            for userdict in get_active_user_dicts_in_realm(user_profile.realm_id)]

# Fetch initial data.  When event_types is not specified, clients want
# all event types.  Whenever you add new code to this function, you
# should also add corresponding events for changes in the data
# structures and new code to apply_events (and add a test in EventsRegisterTest).
def fetch_initial_state_data(user_profile, event_types, queue_id,
                             include_subscribers=True):
    # type: (UserProfile, Optional[Iterable[str]], str, bool) -> Dict[str, Any]
    state = {'queue_id': queue_id}  # type: Dict[str, Any]

    if event_types is None:
        want = lambda msg_type: True
    else:
        want = set(event_types).__contains__

    if want('alert_words'):
        state['alert_words'] = user_alert_words(user_profile)

    if want('custom_profile_fields'):
        fields = custom_profile_fields_for_realm(user_profile.realm.id)
        state['custom_profile_fields'] = [f.as_dict() for f in fields]

    if want('attachments'):
        state['attachments'] = user_attachments(user_profile)

    if want('upload_quota'):
        state['upload_quota'] = user_profile.quota

    if want('total_uploads_size'):
        state['total_uploads_size'] = get_total_uploads_size_for_user(user_profile)

    if want('hotspots'):
        state['hotspots'] = get_next_hotspots(user_profile)

    if want('message'):
        # The client should use get_messages() to fetch messages
        # starting with the max_message_id.  They will get messages
        # newer than that ID via get_events()
        messages = Message.objects.filter(usermessage__user_profile=user_profile).order_by('-id')[:1]
        if messages:
            state['max_message_id'] = messages[0].id
        else:
            state['max_message_id'] = -1

    if want('muted_topics'):
        state['muted_topics'] = get_topic_mutes(user_profile)

    if want('pointer'):
        state['pointer'] = user_profile.pointer

    if want('presence'):
        state['presences'] = get_status_dict(user_profile)

    if want('realm'):
        for property_name in Realm.property_types:
            state['realm_' + property_name] = getattr(user_profile.realm, property_name)

        # Most state is handled via the property_types framework;
        # these manual entries are for those realm settings that don't
        # fit into that framework.
        state['realm_authentication_methods'] = user_profile.realm.authentication_methods_dict()
        state['realm_allow_message_editing'] = user_profile.realm.allow_message_editing
        state['realm_message_content_edit_limit_seconds'] = user_profile.realm.message_content_edit_limit_seconds
        state['realm_icon_url'] = realm_icon_url(user_profile.realm)
        state['realm_icon_source'] = user_profile.realm.icon_source
        state['max_icon_file_size'] = settings.MAX_ICON_FILE_SIZE
        state['realm_bot_domain'] = user_profile.realm.get_bot_domain()
        state['realm_uri'] = user_profile.realm.uri
        state['realm_presence_disabled'] = user_profile.realm.presence_disabled
        state['realm_show_digest_email'] = user_profile.realm.show_digest_email
        state['realm_is_zephyr_mirror_realm'] = user_profile.realm.is_zephyr_mirror_realm
        state['realm_password_auth_enabled'] = password_auth_enabled(user_profile.realm)
        if user_profile.realm.notifications_stream and not user_profile.realm.notifications_stream.deactivated:
            notifications_stream = user_profile.realm.notifications_stream
            state['realm_notifications_stream_id'] = notifications_stream.id
        else:
            state['realm_notifications_stream_id'] = -1

    if want('realm_domains'):
        state['realm_domains'] = get_realm_domains(user_profile.realm)

    if want('realm_emoji'):
        state['realm_emoji'] = user_profile.realm.get_emoji()

    if want('realm_filters'):
        state['realm_filters'] = realm_filters_for_realm(user_profile.realm_id)

    if want('realm_user'):
        state['realm_users'] = get_realm_user_dicts(user_profile)
        state['avatar_source'] = user_profile.avatar_source
        state['avatar_url_medium'] = avatar_url(user_profile, medium=True)
        state['avatar_url'] = avatar_url(user_profile)
        state['can_create_streams'] = user_profile.can_create_streams()
        state['cross_realm_bots'] = list(get_cross_realm_dicts())
        state['is_admin'] = user_profile.is_realm_admin
        state['user_id'] = user_profile.id
        state['enter_sends'] = user_profile.enter_sends
        state['email'] = user_profile.email
        state['full_name'] = user_profile.full_name

    if want('realm_bot'):
        state['realm_bots'] = get_owned_bot_dicts(user_profile)

    if want('subscription'):
        subscriptions, unsubscribed, never_subscribed = gather_subscriptions_helper(
            user_profile, include_subscribers=include_subscribers)
        state['subscriptions'] = subscriptions
        state['unsubscribed'] = unsubscribed
        state['never_subscribed'] = never_subscribed

    if want('update_message_flags') and want('message'):
        # Keeping unread_msgs updated requires both message flag updates and
        # message updates. This is due to the fact that new messages will not
        # generate a flag update so we need to use the flags field in the
        # message event.
        state['unread_msgs'] = get_unread_message_ids_per_recipient(user_profile)

    if want('stream'):
        state['streams'] = do_get_streams(user_profile)
    if want('default_streams'):
        state['realm_default_streams'] = streams_to_dicts_sorted(get_default_streams_for_realm(user_profile.realm_id))

    if want('update_display_settings'):
        for prop in UserProfile.property_types:
            state[prop] = getattr(user_profile, prop)
        state['emojiset_choices'] = user_profile.emojiset_choices()
        state['autoscroll_forever'] = user_profile.autoscroll_forever

    if want('update_global_notifications'):
        for notification in UserProfile.notification_setting_types:
            state[notification] = getattr(user_profile, notification)
        state['default_desktop_notifications'] = user_profile.default_desktop_notifications

    if want('zulip_version'):
        state['zulip_version'] = ZULIP_VERSION

    return state


def remove_message_id_from_unread_mgs(state, remove_id):
    # type: (Dict[str, Dict[str, Any]], int) -> None
    for message_type in ['pms', 'streams', 'huddles']:
        threads = state['unread_msgs'][message_type]
        for obj in threads:
            msg_ids = obj['unread_message_ids']
            if remove_id in msg_ids:
                state['unread_msgs']['count'] -= 1
                msg_ids.remove(remove_id)
        state['unread_msgs'][message_type] = [
            obj for obj in threads
            if obj['unread_message_ids']
        ]

    if remove_id in state['unread_msgs']['mentions']:
        state['unread_msgs']['mentions'].remove(remove_id)

def apply_events(state, events, user_profile, include_subscribers=True,
                 fetch_event_types=None):
    # type: (Dict[str, Any], Iterable[Dict[str, Any]], UserProfile, bool, Optional[Iterable[str]]) -> None
    for event in events:
        if fetch_event_types is not None and event['type'] not in fetch_event_types:
            # TODO: continuing here is not, most precisely, correct.
            # In theory, an event of one type, e.g. `realm_user`,
            # could modify state that doesn't come from that
            # `fetch_event_types` value, e.g. the `our_person` part of
            # that code path.  But it should be extremely rare, and
            # fixing that will require a nontrivial refactor of
            # `apply_event`.  For now, be careful in your choice of
            # `fetch_event_types`.
            continue
        apply_event(state, event, user_profile, include_subscribers)

def apply_event(state, event, user_profile, include_subscribers):
    # type: (Dict[str, Any], Dict[str, Any], UserProfile, bool) -> None
    if event['type'] == "message":
        state['max_message_id'] = max(state['max_message_id'], event['message']['id'])
        if 'unread_msgs' in state:
            apply_unread_message_event(state['unread_msgs'], event['message'])

    elif event['type'] == "hotspots":
        state['hotspots'] = event['hotspots']
    elif event['type'] == "custom_profile_fields":
        state['custom_profile_fields'] = event['fields']
    elif event['type'] == "pointer":
        state['pointer'] = max(state['pointer'], event['pointer'])
    elif event['type'] == "realm_user":
        person = event['person']

        def our_person(p):
            # type: (Dict[str, Any]) -> bool
            return p['user_id'] == person['user_id']

        if event['op'] == "add":
            state['realm_users'].append(person)
        elif event['op'] == "remove":
            state['realm_users'] = [user for user in state['realm_users'] if not our_person(user)]
        elif event['op'] == 'update':
            if (person['user_id'] == user_profile.id and 'avatar_url' in person and 'avatar_url' in state):
                state['avatar_source'] = person['avatar_source']
                state['avatar_url'] = person['avatar_url']
                state['avatar_url_medium'] = person['avatar_url_medium']
            if 'avatar_source' in person:
                # Drop these so that they don't modify the
                # `realm_user` structure in the `p.update()` line
                # later; they're only used in the above lines
                del person['avatar_source']
                del person['avatar_url_medium']

            for field in ['is_admin', 'email', 'full_name']:
                if person['user_id'] == user_profile.id and field in person and field in state:
                    state[field] = person[field]

            for p in state['realm_users']:
                if our_person(p):
                    # In the unlikely event that the current user
                    # just changed to/from being an admin, we need
                    # to add/remove the data on all bots in the
                    # realm.  This is ugly and probably better
                    # solved by removing the all-realm-bots data
                    # given to admin users from this flow.
                    if ('is_admin' in person and 'realm_bots' in state and
                            user_profile.email == person['email']):
                        if p['is_admin'] and not person['is_admin']:
                            state['realm_bots'] = []
                        if not p['is_admin'] and person['is_admin']:
                            state['realm_bots'] = get_owned_bot_dicts(user_profile)

                    # Now update the person
                    p.update(person)
    elif event['type'] == 'realm_bot':
        if event['op'] == 'add':
            state['realm_bots'].append(event['bot'])

        if event['op'] == 'remove':
            email = event['bot']['email']
            for bot in state['realm_bots']:
                if bot['email'] == email:
                    bot['is_active'] = False

        if event['op'] == 'update':
            for bot in state['realm_bots']:
                if bot['email'] == event['bot']['email']:
                    if 'owner_id' in event['bot']:
                        bot['owner'] = get_user_profile_by_id(event['bot']['owner_id']).email
                    else:
                        bot.update(event['bot'])

    elif event['type'] == 'stream':
        if event['op'] == 'create':
            for stream in event['streams']:
                if not stream['invite_only']:
                    stream_data = copy.deepcopy(stream)
                    if include_subscribers:
                        stream_data['subscribers'] = []
                    # Add stream to never_subscribed (if not invite_only)
                    state['never_subscribed'].append(stream_data)
                state['streams'].append(stream)
            state['streams'].sort(key=lambda elt: elt["name"])

        if event['op'] == 'delete':
            deleted_stream_ids = {stream['stream_id'] for stream in event['streams']}
            state['streams'] = [s for s in state['streams'] if s['stream_id'] not in deleted_stream_ids]
            state['never_subscribed'] = [stream for stream in state['never_subscribed'] if
                                         stream['stream_id'] not in deleted_stream_ids]

        if event['op'] == 'update':
            # For legacy reasons, we call stream data 'subscriptions' in
            # the state var here, for the benefit of the JS code.
            for obj in state['subscriptions']:
                if obj['name'].lower() == event['name'].lower():
                    obj[event['property']] = event['value']
            # Also update the pure streams data
            for stream in state['streams']:
                if stream['name'].lower() == event['name'].lower():
                    prop = event['property']
                    if prop in stream:
                        stream[prop] = event['value']
        elif event['op'] == "occupy":
            state['streams'] += event['streams']
        elif event['op'] == "vacate":
            stream_ids = [s["stream_id"] for s in event['streams']]
            state['streams'] = [s for s in state['streams'] if s["stream_id"] not in stream_ids]
    elif event['type'] == 'default_streams':
        state['realm_default_streams'] = event['default_streams']
    elif event['type'] == 'realm':
        if event['op'] == "update":
            field = 'realm_' + event['property']
            state[field] = event['value']

            # Tricky interaction: Whether we can create streams can get changed here.
            if (field in ['realm_create_stream_by_admins_only',
                          'realm_waiting_period_threshold']) and 'can_create_streams' in state:
                state['can_create_streams'] = user_profile.can_create_streams()
        elif event['op'] == "update_dict":
            for key, value in event['data'].items():
                state['realm_' + key] = value
                # It's a bit messy, but this is where we need to
                # update the state for whether password authentication
                # is enabled on this server.
                if key == 'authentication_methods':
                    state['realm_password_auth_enabled'] = (value['Email'] or value['LDAP'])
    elif event['type'] == "subscription":
        if not include_subscribers and event['op'] in ['peer_add', 'peer_remove']:
            return

        if event['op'] in ["add"]:
            if include_subscribers:
                # Convert the emails to user_profile IDs since that's what register() returns
                # TODO: Clean up this situation by making the event also have IDs
                for item in event["subscriptions"]:
                    item["subscribers"] = [
                        get_user(email, user_profile.realm).id
                        for email in item["subscribers"]
                    ]
            else:
                # Avoid letting 'subscribers' entries end up in the list
                for i, sub in enumerate(event['subscriptions']):
                    event['subscriptions'][i] = copy.deepcopy(event['subscriptions'][i])
                    del event['subscriptions'][i]['subscribers']

        def name(sub):
            # type: (Dict[str, Any]) -> Text
            return sub['name'].lower()

        if event['op'] == "add":
            added_names = set(map(name, event["subscriptions"]))
            was_added = lambda s: name(s) in added_names

            # add the new subscriptions
            state['subscriptions'] += event['subscriptions']

            # remove them from unsubscribed if they had been there
            state['unsubscribed'] = [s for s in state['unsubscribed'] if not was_added(s)]

            # remove them from never_subscribed if they had been there
            state['never_subscribed'] = [s for s in state['never_subscribed'] if not was_added(s)]

        elif event['op'] == "remove":
            removed_names = set(map(name, event["subscriptions"]))
            was_removed = lambda s: name(s) in removed_names

            # Find the subs we are affecting.
            removed_subs = list(filter(was_removed, state['subscriptions']))

            # Remove our user from the subscribers of the removed subscriptions.
            if include_subscribers:
                for sub in removed_subs:
                    sub['subscribers'] = [id for id in sub['subscribers'] if id != user_profile.id]

            # We must effectively copy the removed subscriptions from subscriptions to
            # unsubscribe, since we only have the name in our data structure.
            state['unsubscribed'] += removed_subs

            # Now filter out the removed subscriptions from subscriptions.
            state['subscriptions'] = [s for s in state['subscriptions'] if not was_removed(s)]

        elif event['op'] == 'update':
            for sub in state['subscriptions']:
                if sub['name'].lower() == event['name'].lower():
                    sub[event['property']] = event['value']
        elif event['op'] == 'peer_add':
            user_id = event['user_id']
            for sub in state['subscriptions']:
                if (sub['name'] in event['subscriptions'] and
                        user_id not in sub['subscribers']):
                    sub['subscribers'].append(user_id)
            for sub in state['never_subscribed']:
                if (sub['name'] in event['subscriptions'] and
                        user_id not in sub['subscribers']):
                    sub['subscribers'].append(user_id)
        elif event['op'] == 'peer_remove':
            user_id = event['user_id']
            for sub in state['subscriptions']:
                if (sub['name'] in event['subscriptions'] and
                        user_id in sub['subscribers']):
                    sub['subscribers'].remove(user_id)
    elif event['type'] == "presence":
        # TODO: Add user_id to presence update events / state format!
        presence_user_profile = get_user(event['email'], user_profile.realm)
        state['presences'][event['email']] = UserPresence.get_status_dict_by_user(presence_user_profile)[event['email']]
    elif event['type'] == "update_message":
        # The client will get the updated message directly, but we need to
        # update the subjects of our unread message ids
        if 'subject' in event and 'unread_msgs' in state:
            for obj in state['unread_msgs']['streams']:
                if obj['stream_id'] == event['stream_id']:
                    if obj['topic'] == event['orig_subject']:
                        obj['topic'] = event['subject']
    elif event['type'] == "delete_message":
        max_message = Message.objects.filter(
            usermessage__user_profile=user_profile).order_by('-id').first()
        if max_message:
            state['max_message_id'] = max_message.id
        else:
            state['max_message_id'] = -1

        remove_id = event['message_id']
        remove_message_id_from_unread_mgs(state, remove_id)
    elif event['type'] == "reaction":
        # The client will get the message with the reactions directly
        pass
    elif event['type'] == 'typing':
        # Typing notification events are transient and thus ignored
        pass
    elif event['type'] == "update_message_flags":
        # The client will get the message with the updated flags directly but
        # we need to keep the unread_msgs updated.
        if event['flag'] == 'read' and event['operation'] == 'add':
            for remove_id in event['messages']:
                remove_message_id_from_unread_mgs(state, remove_id)
    elif event['type'] == "realm_domains":
        if event['op'] == 'add':
            state['realm_domains'].append(event['realm_domain'])
        elif event['op'] == 'change':
            for realm_domain in state['realm_domains']:
                if realm_domain['domain'] == event['realm_domain']['domain']:
                    realm_domain['allow_subdomains'] = event['realm_domain']['allow_subdomains']
        elif event['op'] == 'remove':
            state['realm_domains'] = [realm_domain for realm_domain in state['realm_domains']
                                      if realm_domain['domain'] != event['domain']]
    elif event['type'] == "realm_emoji":
        state['realm_emoji'] = event['realm_emoji']
    elif event['type'] == "alert_words":
        state['alert_words'] = event['alert_words']
    elif event['type'] == "muted_topics":
        state['muted_topics'] = event["muted_topics"]
    elif event['type'] == "realm_filters":
        state['realm_filters'] = event["realm_filters"]
    elif event['type'] == "update_display_settings":
        assert event['setting_name'] in UserProfile.property_types
        state[event['setting_name']] = event['setting']
    elif event['type'] == "update_global_notifications":
        assert event['notification_name'] in UserProfile.notification_setting_types
        state[event['notification_name']] = event['setting']
    else:
        raise AssertionError("Unexpected event type %s" % (event['type'],))

def do_events_register(user_profile, user_client, apply_markdown=True,
                       event_types=None, queue_lifespan_secs=0, all_public_streams=False,
                       include_subscribers=True, narrow=[], fetch_event_types=None):
    # type: (UserProfile, Client, bool, Optional[Iterable[str]], int, bool, bool, Iterable[Sequence[Text]], Optional[Iterable[str]]) -> Dict[str, Any]

    # Technically we don't need to check this here because
    # build_narrow_filter will check it, but it's nicer from an error
    # handling perspective to do it before contacting Tornado
    check_supported_events_narrow_filter(narrow)

    # Note that we pass event_types, not fetch_event_types here, since
    # that's what controls which future events are sent.
    queue_id = request_event_queue(user_profile, user_client, apply_markdown,
                                   queue_lifespan_secs, event_types, all_public_streams,
                                   narrow=narrow)

    if queue_id is None:
        raise JsonableError(_("Could not allocate event queue"))

    if fetch_event_types is not None:
        event_types_set = set(fetch_event_types)  # type: Optional[Set[str]]
    elif event_types is not None:
        event_types_set = set(event_types)
    else:
        event_types_set = None

    # Fill up the UserMessage rows if a soft-deactivated user has returned
    maybe_catch_up_soft_deactivated_user(user_profile)

    ret = fetch_initial_state_data(user_profile, event_types_set, queue_id,
                                   include_subscribers=include_subscribers)

    # Apply events that came in while we were fetching initial data
    events = get_user_events(user_profile, queue_id, -1)
    apply_events(ret, events, user_profile, include_subscribers=include_subscribers,
                 fetch_event_types=fetch_event_types)

    if len(events) > 0:
        ret['last_event_id'] = events[-1]['id']
    else:
        ret['last_event_id'] = -1
    return ret
