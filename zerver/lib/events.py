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
    Any, Dict, Iterable, List, Optional, Sequence, Set, Text, Tuple
)

session_engine = import_module(settings.SESSION_ENGINE)

from zerver.lib.alert_words import user_alert_words
from zerver.lib.attachments import user_attachments
from zerver.lib.avatar import get_avatar_url
from zerver.lib.narrow import check_supported_events_narrow_filter
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.request import JsonableError
from zerver.lib.actions import validate_user_access_to_subscribers_helper, \
    do_get_streams, get_default_streams_for_realm, \
    gather_subscriptions_helper, get_realm_aliases, \
    get_status_dict, streams_to_dicts_sorted
from zerver.tornado.event_queue import request_event_queue, get_user_events
from zerver.models import Client, Message, UserProfile, \
    get_user_profile_by_email, get_user_profile_by_id, \
    get_active_user_dicts_in_realm, realm_filters_for_realm, \
    get_owned_bot_dicts
from version import ZULIP_VERSION


def get_realm_user_dicts(user_profile):
    # type: (UserProfile) -> List[Dict[str, Text]]
    def avatar_url(userdict):
        # type: (Dict[str, Any]) -> Text
        return get_avatar_url(userdict['avatar_source'],
                              userdict['email'],
                              userdict['avatar_version'],
                              )

    return [{'email': userdict['email'],
             'user_id': userdict['id'],
             'avatar_url': avatar_url(userdict),
             'is_admin': userdict['is_realm_admin'],
             'is_bot': userdict['is_bot'],
             'full_name': userdict['full_name']}
            for userdict in get_active_user_dicts_in_realm(user_profile.realm)]

# Fetch initial data.  When event_types is not specified, clients want
# all event types.  Whenever you add new code to this function, you
# should also add corresponding events for changes in the data
# structures and new code to apply_events (and add a test in EventsRegisterTest).
def fetch_initial_state_data(user_profile, event_types, queue_id,
                             include_subscribers=True):
    # type: (UserProfile, Optional[Iterable[str]], str, bool) -> Dict[str, Any]
    state = {'queue_id': queue_id} # type: Dict[str, Any]

    if event_types is None:
        want = lambda msg_type: True
    else:
        want = set(event_types).__contains__

    if want('alert_words'):
        state['alert_words'] = user_alert_words(user_profile)

    if want('attachments'):
        state['attachments'] = user_attachments(user_profile)

    if want('message'):
        # The client should use get_old_messages() to fetch messages
        # starting with the max_message_id.  They will get messages
        # newer than that ID via get_events()
        messages = Message.objects.filter(usermessage__user_profile=user_profile).order_by('-id')[:1]
        if messages:
            state['max_message_id'] = messages[0].id
        else:
            state['max_message_id'] = -1

    if want('muted_topics'):
        state['muted_topics'] = ujson.loads(user_profile.muted_topics)

    if want('pointer'):
        state['pointer'] = user_profile.pointer

    if want('presence'):
        state['presences'] = get_status_dict(user_profile)

    if want('realm'):
        state['realm_name'] = user_profile.realm.name
        state['realm_restricted_to_domain'] = user_profile.realm.restricted_to_domain
        state['realm_invite_required'] = user_profile.realm.invite_required
        state['realm_invite_by_admins_only'] = user_profile.realm.invite_by_admins_only
        state['realm_authentication_methods'] = user_profile.realm.authentication_methods_dict()
        state['realm_create_stream_by_admins_only'] = user_profile.realm.create_stream_by_admins_only
        state['realm_add_emoji_by_admins_only'] = user_profile.realm.add_emoji_by_admins_only
        state['realm_allow_message_editing'] = user_profile.realm.allow_message_editing
        state['realm_message_content_edit_limit_seconds'] = user_profile.realm.message_content_edit_limit_seconds
        state['realm_default_language'] = user_profile.realm.default_language
        state['realm_waiting_period_threshold'] = user_profile.realm.waiting_period_threshold
        state['realm_icon_url'] = realm_icon_url(user_profile.realm)
        state['realm_icon_source'] = user_profile.realm.icon_source
        state['realm_name_changes_disabled'] = user_profile.realm.name_changes_disabled
        state['realm_email_changes_disabled'] = user_profile.realm.email_changes_disabled
        state['max_icon_file_size'] = settings.MAX_ICON_FILE_SIZE
        state['realm_bot_domain'] = user_profile.realm.get_bot_domain()

    if want('realm_domains'):
        state['realm_domains'] = get_realm_aliases(user_profile.realm)

    if want('realm_emoji'):
        state['realm_emoji'] = user_profile.realm.get_emoji()

    if want('realm_filters'):
        state['realm_filters'] = realm_filters_for_realm(user_profile.realm_id)

    if want('realm_user'):
        state['realm_users'] = get_realm_user_dicts(user_profile)

    if want('realm_bot'):
        state['realm_bots'] = get_owned_bot_dicts(user_profile)

    if want('referral'):
        state['referrals'] = {'granted': user_profile.invites_granted,
                              'used': user_profile.invites_used}

    if want('subscription'):
        subscriptions, unsubscribed, never_subscribed = gather_subscriptions_helper(
            user_profile, include_subscribers=include_subscribers)
        state['subscriptions'] = subscriptions
        state['unsubscribed'] = unsubscribed
        state['never_subscribed'] = never_subscribed

    if want('update_message_flags'):
        # There's no initial data for message flag updates, client will
        # get any updates during a session from get_events()
        pass

    if want('stream'):
        state['streams'] = do_get_streams(user_profile)
    if want('default_streams'):
        state['realm_default_streams'] = streams_to_dicts_sorted(get_default_streams_for_realm(user_profile.realm))

    if want('update_display_settings'):
        state['twenty_four_hour_time'] = user_profile.twenty_four_hour_time
        state['left_side_userlist'] = user_profile.left_side_userlist
        state['emoji_alt_code'] = user_profile.emoji_alt_code

        default_language = user_profile.default_language
        state['default_language'] = default_language

    if want('update_global_notifications'):
        state['enable_stream_desktop_notifications'] = user_profile.enable_stream_desktop_notifications
        state['enable_stream_sounds'] = user_profile.enable_stream_sounds
        state['enable_desktop_notifications'] = user_profile.enable_desktop_notifications
        state['enable_sounds'] = user_profile.enable_sounds
        state['enable_offline_email_notifications'] = user_profile.enable_offline_email_notifications
        state['enable_offline_push_notifications'] = user_profile.enable_offline_push_notifications
        state['enable_online_push_notifications'] = user_profile.enable_online_push_notifications
        state['enable_digest_emails'] = user_profile.enable_digest_emails

    if want('zulip_version'):
        state['zulip_version'] = ZULIP_VERSION

    return state

def apply_events(state, events, user_profile, include_subscribers=True):
    # type: (Dict[str, Any], Iterable[Dict[str, Any]], UserProfile, bool) -> None
    for event in events:
        apply_event(state, event, user_profile, include_subscribers)

def apply_event(state, event, user_profile, include_subscribers):
    # type: (Dict[str, Any], Dict[str, Any], UserProfile, bool) -> None
    if event['type'] == "message":
        state['max_message_id'] = max(state['max_message_id'], event['message']['id'])
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
        elif event['op'] == "update_dict":
            for key, value in event['data'].items():
                state['realm_' + key] = value
    elif event['type'] == "subscription":
        if not include_subscribers and event['op'] in ['peer_add', 'peer_remove']:
            return

        if event['op'] in ["add"]:
            if include_subscribers:
                # Convert the emails to user_profile IDs since that's what register() returns
                # TODO: Clean up this situation by making the event also have IDs
                for item in event["subscriptions"]:
                    item["subscribers"] = [get_user_profile_by_email(email).id for email in item["subscribers"]]
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
        state['presences'][event['email']] = event['presence']
    elif event['type'] == "update_message":
        # The client will get the updated message directly
        pass
    elif event['type'] == "reaction":
        # The client will get the message with the reactions directly
        pass
    elif event['type'] == "referral":
        state['referrals'] = event['referrals']
    elif event['type'] == "update_message_flags":
        # The client will get the message with the updated flags directly
        pass
    elif event['type'] == "realm_domains":
        if event['op'] == 'add':
            state['realm_domains'].append(event['alias'])
        elif event['op'] == 'change':
            for realm_domain in state['realm_domains']:
                if realm_domain['domain'] == event['alias']['domain']:
                    realm_domain['allow_subdomains'] = event['alias']['allow_subdomains']
        elif event['op'] == 'remove':
            state['realm_domains'] = [alias for alias in state['realm_domains'] if alias['domain'] != event['domain']]
    elif event['type'] == "realm_emoji":
        state['realm_emoji'] = event['realm_emoji']
    elif event['type'] == "alert_words":
        state['alert_words'] = event['alert_words']
    elif event['type'] == "muted_topics":
        state['muted_topics'] = event["muted_topics"]
    elif event['type'] == "realm_filters":
        state['realm_filters'] = event["realm_filters"]
    elif event['type'] == "update_display_settings":
        if event['setting_name'] == "twenty_four_hour_time":
            state['twenty_four_hour_time'] = event["setting"]
        if event['setting_name'] == 'left_side_userlist':
            state['left_side_userlist'] = event["setting"]
        if event['setting_name'] == 'emoji_alt_code':
            state['emoji_alt_code'] = event["setting"]
    elif event['type'] == "update_global_notifications":
        if event['notification_name'] == "enable_stream_desktop_notifications":
            state['enable_stream_desktop_notifications'] = event['setting']
        elif event['notification_name'] == "enable_stream_sounds":
            state['enable_stream_sounds'] = event['setting']
        elif event['notification_name'] == "enable_desktop_notifications":
            state['enable_desktop_notifications'] = event['setting']
        elif event['notification_name'] == "enable_sounds":
            state['enable_sounds'] = event['setting']
        elif event['notification_name'] == "enable_offline_email_notifications":
            state['enable_offline_email_notifications'] = event['setting']
        elif event['notification_name'] == "enable_offline_push_notifications":
            state['enable_offline_push_notifications'] = event['setting']
        elif event['notification_name'] == "enable_online_push_notifications":
            state['enable_online_push_notifications'] = event['setting']
        elif event['notification_name'] == "enable_digest_emails":
            state['enable_digest_emails'] = event['setting']
    else:
        raise ValueError("Unexpected event type %s" % (event['type'],))

def do_events_register(user_profile, user_client, apply_markdown=True,
                       event_types=None, queue_lifespan_secs=0, all_public_streams=False,
                       include_subscribers=True, narrow=[]):
    # type: (UserProfile, Client, bool, Optional[Iterable[str]], int, bool, bool, Iterable[Sequence[Text]]) -> Dict[str, Any]
    # Technically we don't need to check this here because
    # build_narrow_filter will check it, but it's nicer from an error
    # handling perspective to do it before contacting Tornado
    check_supported_events_narrow_filter(narrow)
    queue_id = request_event_queue(user_profile, user_client, apply_markdown,
                                   queue_lifespan_secs, event_types, all_public_streams,
                                   narrow=narrow)

    if queue_id is None:
        raise JsonableError(_("Could not allocate event queue"))
    if event_types is not None:
        event_types_set = set(event_types) # type: Optional[Set[str]]
    else:
        event_types_set = None

    ret = fetch_initial_state_data(user_profile, event_types_set, queue_id,
                                   include_subscribers=include_subscribers)

    # Apply events that came in while we were fetching initial data
    events = get_user_events(user_profile, queue_id, -1)
    apply_events(ret, events, user_profile, include_subscribers=include_subscribers)
    if len(events) > 0:
        ret['last_event_id'] = events[-1]['id']
    else:
        ret['last_event_id'] = -1
    return ret
