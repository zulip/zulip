# -*- coding: utf-8 -*-
from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.lib.slack_data_to_zulip_data import (
    rm_tree,
    get_slack_api_data,
    build_zerver_realm,
    get_user_email,
    build_avatar_url,
    build_avatar,
    get_admin,
    get_user_timezone,
    users_to_zerver_userprofile,
    build_defaultstream,
    build_pm_recipient_sub_from_user,
    build_subscription,
    channels_to_zerver_stream,
    slack_workspace_to_realm,
    get_message_sending_user,
    build_zerver_usermessage,
    channel_message_to_zerver_message,
    convert_slack_workspace_messages,
    do_convert_data,
    process_avatars,
)
from zerver.lib.import_realm import (
    do_import_realm,
)
from zerver.lib.avatar_hash import (
    user_avatar_path_from_ids,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.models import (
    Realm,
    get_realm,
)
from zerver.lib import mdiff

import ujson
import json
import logging
import shutil
import requests
import os
import mock
from typing import Any, AnyStr, Dict, List, Optional, Set, Tuple, Text

def remove_folder(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)

# This method will be used by the mock to replace requests.get
def mocked_requests_get(*args: List[str], **kwargs: List[str]) -> mock.Mock:
    class MockResponse:
        def __init__(self, json_data: Dict[str, Any], status_code: int) -> None:
            self.json_data = json_data
            self.status_code = status_code

        def json(self) -> Dict[str, Any]:
            return self.json_data

    if args[0] == 'https://slack.com/api/users.list?token=valid-token':
        return MockResponse({"members": "user_data"}, 200)
    elif args[0] == 'https://slack.com/api/users.list?token=invalid-token':
        return MockResponse({"ok": False, "error": "invalid_auth"}, 200)
    else:
        return MockResponse(None, 404)

class SlackImporter(ZulipTestCase):
    logger = logging.getLogger()
    # set logger to a higher level to suppress 'logger.INFO' outputs
    logger.setLevel(logging.WARNING)

    @mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_get_slack_api_data(self, mock_get: mock.Mock) -> None:
        token = 'valid-token'
        slack_user_list_url = "https://slack.com/api/users.list"
        self.assertEqual(get_slack_api_data(token, slack_user_list_url, "members"),
                         "user_data")
        token = 'invalid-token'
        with self.assertRaises(Exception) as invalid:
            get_slack_api_data(token, slack_user_list_url, "members")
        self.assertEqual(invalid.exception.args, ('Enter a valid token!',),)

        token = 'status404'
        wrong_url = "https://slack.com/api/wrong"
        with self.assertRaises(Exception) as invalid:
            get_slack_api_data(token, wrong_url, "members")
        self.assertEqual(invalid.exception.args, ('Something went wrong. Please try again!',),)

    def test_build_zerver_realm(self) -> None:
        realm_id = 2
        realm_subdomain = "test-realm"
        time = float(timezone_now().timestamp())
        test_realm = build_zerver_realm(realm_id, realm_subdomain, time)
        test_zerver_realm_dict = test_realm[0]

        self.assertEqual(test_zerver_realm_dict['id'], realm_id)
        self.assertEqual(test_zerver_realm_dict['string_id'], realm_subdomain)
        self.assertEqual(test_zerver_realm_dict['name'], realm_subdomain)
        self.assertEqual(test_zerver_realm_dict['date_created'], time)

    def test_get_admin(self) -> None:
        user_data = [{'is_admin': True, 'is_owner': False, 'is_primary_owner': False},
                     {'is_admin': True, 'is_owner': True, 'is_primary_owner': False},
                     {'is_admin': True, 'is_owner': True, 'is_primary_owner': True},
                     {'is_admin': False, 'is_owner': False, 'is_primary_owner': False}]
        self.assertEqual(get_admin(user_data[0]), True)
        self.assertEqual(get_admin(user_data[1]), True)
        self.assertEqual(get_admin(user_data[2]), True)
        self.assertEqual(get_admin(user_data[3]), False)

    def test_get_timezone(self) -> None:
        user_chicago_timezone = {"tz": "America\/Chicago"}
        user_timezone_none = {"tz": None}
        user_no_timezone = {}  # type: Dict[str, Any]

        self.assertEqual(get_user_timezone(user_chicago_timezone), "America\/Chicago")
        self.assertEqual(get_user_timezone(user_timezone_none), "America/New_York")
        self.assertEqual(get_user_timezone(user_no_timezone), "America/New_York")

    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_data_file")
    def test_users_to_zerver_userprofile(self, mock_get_data_file: mock.Mock) -> None:
        custom_profile_field_user1 = {"Xf06054BBB": {"value": "random1"},
                                      "Xf023DSCdd": {"value": "employee"}}
        custom_profile_field_user2 = {"Xf06054BBB": {"value": "random2"},
                                      "Xf023DSCdd": {"value": "employer"}}
        user_data = [{"id": "U08RGD1RD",
                      "team_id": "T5YFFM2QY",
                      "name": "john",
                      "deleted": False,
                      "real_name": "John Doe",
                      "profile": {"image_32": "", "email": "jon@gmail.com", "avatar_hash": "hash",
                                  "fields": custom_profile_field_user1}},
                     {"id": "U0CBK5KAT",
                      "team_id": "T5YFFM2QY",
                      "is_admin": True,
                      "is_bot": False,
                      "is_owner": True,
                      "is_primary_owner": True,
                      'name': 'Jane',
                      "real_name": "Jane Doe",
                      "deleted": False,
                      "profile": {"image_32": "https:\/\/secure.gravatar.com\/avatar\/random.png",
                                  "fields": custom_profile_field_user2,
                                  "email": "jane@foo.com", "avatar_hash": "hash"}},
                     {"id": "U09TYF5Sk",
                      "team_id": "T5YFFM2QY",
                      "name": "Bot",
                      "real_name": "Bot",
                      "is_bot": True,
                      "deleted": False,
                      "profile": {"image_32": "https:\/\/secure.gravatar.com\/avatar\/random1.png",
                                  "email": "bot1@zulipchat.com", "avatar_hash": "hash"}}]

        mock_get_data_file.return_value = user_data
        # As user with slack_id 'U0CBK5KAT' is the primary owner, that user should be imported first
        # and hence has zulip_id = 1
        test_added_users = {'U08RGD1RD': 1,
                            'U0CBK5KAT': 0,
                            'U09TYF5Sk': 2}
        slack_data_dir = './random_path'
        timestamp = int(timezone_now().timestamp())
        mock_get_data_file.return_value = user_data
        zerver_userprofile, avatar_list, added_users, customprofilefield, \
            customprofilefield_value = users_to_zerver_userprofile(slack_data_dir, user_data, 1,
                                                                   timestamp, 'test_domain')

        # Test custom profile fields
        self.assertEqual(customprofilefield[0]['field_type'], 1)
        self.assertEqual(customprofilefield[1]['name'], 'slack custom field 2')

        self.assertEqual(len(customprofilefield_value), 4)
        self.assertEqual(customprofilefield_value[0]['field'], 0)
        self.assertEqual(customprofilefield_value[0]['user_profile'], 1)
        self.assertEqual(customprofilefield_value[2]['user_profile'], 0)

        # test that the primary owner should always be imported first
        self.assertDictEqual(added_users, test_added_users)
        self.assertEqual(len(avatar_list), 3)

        self.assertEqual(zerver_userprofile[1]['id'], test_added_users['U0CBK5KAT'])
        self.assertEqual(len(zerver_userprofile), 3)
        self.assertEqual(zerver_userprofile[1]['id'], 0)
        self.assertEqual(zerver_userprofile[1]['is_realm_admin'], True)
        self.assertEqual(zerver_userprofile[1]['is_staff'], False)
        self.assertEqual(zerver_userprofile[1]['is_active'], True)
        self.assertEqual(zerver_userprofile[0]['is_staff'], False)
        self.assertEqual(zerver_userprofile[0]['is_bot'], False)
        self.assertEqual(zerver_userprofile[0]['enable_desktop_notifications'], True)
        self.assertEqual(zerver_userprofile[2]['bot_type'], 1)
        self.assertEqual(zerver_userprofile[2]['avatar_source'], 'U')

    def test_build_defaultstream(self) -> None:
        realm_id = 1
        stream_id = 1
        default_channel_general = build_defaultstream('general', realm_id, stream_id, 1)
        test_default_channel = {'stream': 1, 'realm': 1, 'id': 1}
        self.assertDictEqual(test_default_channel, default_channel_general)
        default_channel_general = build_defaultstream('random', realm_id, stream_id, 1)
        test_default_channel = {'stream': 1, 'realm': 1, 'id': 1}
        self.assertDictEqual(test_default_channel, default_channel_general)

    def test_build_pm_recipient_sub_from_user(self) -> None:
        zulip_user_id = 3
        recipient_id = 5
        subscription_id = 7
        recipient, sub = build_pm_recipient_sub_from_user(zulip_user_id, recipient_id, subscription_id)

        self.assertEqual(recipient['id'], sub['recipient'])
        self.assertEqual(recipient['type_id'], sub['user_profile'])

        self.assertEqual(recipient['type'], 1)
        self.assertEqual(recipient['type_id'], 3)

        self.assertEqual(sub['recipient'], 5)
        self.assertEqual(sub['id'], 7)
        self.assertEqual(sub['active'], True)

    def test_build_subscription(self) -> None:
        channel_members = ["U061A1R2R", "U061A3E0G", "U061A5N1G", "U064KUGRJ"]
        added_users = {"U061A1R2R": 1, "U061A3E0G": 8, "U061A5N1G": 7, "U064KUGRJ": 5}
        subscription_id_count = 0
        recipient_id = 12
        zerver_subscription = []  # type: List[Dict[str, Any]]
        final_subscription_id = build_subscription(channel_members, zerver_subscription,
                                                   recipient_id, added_users,
                                                   subscription_id_count)
        # sanity checks
        self.assertEqual(final_subscription_id, 4)
        self.assertEqual(zerver_subscription[0]['recipient'], 12)
        self.assertEqual(zerver_subscription[0]['id'], 0)
        self.assertEqual(zerver_subscription[0]['user_profile'], added_users[channel_members[0]])
        self.assertEqual(zerver_subscription[2]['user_profile'], added_users[channel_members[2]])
        self.assertEqual(zerver_subscription[3]['id'], 3)
        self.assertEqual(zerver_subscription[1]['recipient'],
                         zerver_subscription[3]['recipient'])
        self.assertEqual(zerver_subscription[1]['pin_to_top'], False)

    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_data_file")
    def test_channels_to_zerver_stream(self, mock_get_data_file: mock.Mock) -> None:

        added_users = {"U061A1R2R": 1, "U061A3E0G": 8, "U061A5N1G": 7, "U064KUGRJ": 5}
        zerver_userprofile = [{'id': 1}, {'id': 8}, {'id': 7}, {'id': 5}]
        realm_id = 3

        channel_data = [{'id': "C061A0WJG", 'name': 'random', 'created': '1433558319',
                         'is_general': False, 'members': ['U061A1R2R', 'U061A5N1G'],
                         'is_archived': True, 'topic': {'value': 'random'},
                         'purpose': {'value': 'no purpose'}},
                        {'id': "C061A0YJG", 'name': 'general', 'created': '1433559319',
                         'is_general': False, 'is_archived': False,
                         'members': ['U061A1R2R', 'U061A5N1G', 'U064KUGRJ'],
                         'topic': {'value': 'general'}, 'purpose': {'value': 'general'}},
                        {'id': "C061A0YJP", 'name': 'general1', 'created': '1433559319',
                         'is_general': False, 'is_archived': False,
                         'members': ['U061A1R2R'],
                         'topic': {'value': 'general channel'}, 'purpose': {'value': 'For everyone'}},
                        {'id': "C061A0HJG", 'name': 'feedback', 'created': '1433558359',
                         'is_general': False, 'members': ['U061A3E0G'], 'is_archived': False,
                         'topic': {'value': ''}, 'purpose': {'value': ''}}]
        mock_get_data_file.return_value = channel_data

        channel_to_zerver_stream_output = channels_to_zerver_stream('./random_path', realm_id, added_users,
                                                                    zerver_userprofile)
        zerver_defaultstream = channel_to_zerver_stream_output[0]
        zerver_stream = channel_to_zerver_stream_output[1]
        added_channels = channel_to_zerver_stream_output[2]
        zerver_subscription = channel_to_zerver_stream_output[3]
        zerver_recipient = channel_to_zerver_stream_output[4]
        added_recipient = channel_to_zerver_stream_output[5]

        test_added_channels = {'feedback': ("C061A0HJG", 3), 'general': ("C061A0YJG", 1),
                               'general1': ("C061A0YJP", 2), 'random': ("C061A0WJG", 0)}
        test_added_recipient = {'feedback': 3, 'general': 1, 'general1': 2, 'random': 0}

        # zerver defaultstream already tested in helper functions
        self.assertEqual(zerver_defaultstream, [{'id': 0, 'realm': 3, 'stream': 0},
                                                {'id': 1, 'realm': 3, 'stream': 1}])

        self.assertDictEqual(test_added_channels, added_channels)
        self.assertDictEqual(test_added_recipient, added_recipient)

        # functioning of zerver subscriptions are already tested in the helper functions
        # This is to check the concatenation of the output lists from the helper functions
        # subscriptions for stream
        self.assertEqual(zerver_subscription[3]['recipient'], 1)
        self.assertEqual(zerver_subscription[5]['recipient'], 2)
        # subscription for users
        self.assertEqual(zerver_subscription[6]['recipient'], 3)
        self.assertEqual(zerver_subscription[7]['user_profile'], 1)

        # recipients for stream
        self.assertEqual(zerver_recipient[1]['id'], zerver_subscription[3]['recipient'])
        self.assertEqual(zerver_recipient[2]['type_id'], zerver_stream[2]['id'])
        self.assertEqual(zerver_recipient[0]['type'], 2)
        # recipients for users (already tested in helped function)
        self.assertEqual(zerver_recipient[3]['type'], 2)
        self.assertEqual(zerver_recipient[4]['type'], 1)

        # stream mapping
        self.assertEqual(zerver_stream[0]['name'], channel_data[0]['name'])
        self.assertEqual(zerver_stream[0]['deactivated'], channel_data[0]['is_archived'])
        self.assertEqual(zerver_stream[0]['description'], 'no purpose')
        self.assertEqual(zerver_stream[0]['invite_only'], False)
        self.assertEqual(zerver_stream[0]['realm'], realm_id)
        self.assertEqual(zerver_stream[2]['id'],
                         test_added_channels[zerver_stream[2]['name']][1])

    @mock.patch("zerver.lib.slack_data_to_zulip_data.build_zerver_realm", return_value=[{}])
    @mock.patch("zerver.lib.slack_data_to_zulip_data.users_to_zerver_userprofile",
                return_value=[[], [], {}, [], []])
    @mock.patch("zerver.lib.slack_data_to_zulip_data.channels_to_zerver_stream",
                return_value=[[], [], {}, [], [], {}])
    def test_slack_workspace_to_realm(self, mock_channels_to_zerver_stream: mock.Mock,
                                      mock_users_to_zerver_userprofile: mock.Mock,
                                      mock_build_zerver_realm: mock.Mock) -> None:

        realm_id = 1
        user_list = []  # type: List[Dict[str, Any]]
        realm, added_users, added_recipient, added_channels, avatar_list, em = slack_workspace_to_realm(
            'testdomain', realm_id, user_list, 'test-realm', './random_path', {})
        test_zerver_realmdomain = [{'realm': realm_id, 'allow_subdomains': False,
                                    'domain': 'testdomain', 'id': realm_id}]
        # Functioning already tests in helper functions
        self.assertEqual(added_users, {})
        self.assertEqual(added_channels, {})
        self.assertEqual(added_recipient, {})
        self.assertEqual(avatar_list, [])

        zerver_realmdomain = realm['zerver_realmdomain']
        self.assertListEqual(zerver_realmdomain, test_zerver_realmdomain)
        self.assertEqual(realm['zerver_userpresence'], [])
        self.assertEqual(realm['zerver_stream'], [])
        self.assertEqual(realm['zerver_userprofile'], [])
        self.assertEqual(realm['zerver_realm'], [{}])

    def test_get_message_sending_user(self) -> None:
        message_with_file = {'subtype': 'file', 'type': 'message',
                             'file': {'user': 'U064KUGRJ'}}
        message_without_file = {'subtype': 'file', 'type': 'messge', 'user': 'U064KUGRJ'}

        user_file = get_message_sending_user(message_with_file)
        self.assertEqual(user_file, 'U064KUGRJ')
        user_without_file = get_message_sending_user(message_without_file)
        self.assertEqual(user_without_file, 'U064KUGRJ')

    def test_build_zerver_message(self) -> None:
        zerver_usermessage = []  # type: List[Dict[str, Any]]
        usermessage_id_count = 0
        zerver_subscription = [{'recipient': 2, 'user_profile': 7},
                               {'recipient': 4, 'user_profile': 12},
                               {'recipient': 2, 'user_profile': 16},
                               {'recipient': 2, 'user_profile': 15},
                               {'recipient': 2, 'user_profile': 3}]
        recipient_id = 2
        mentioned_users_id = [12, 3, 16]
        message_id = 9

        test_usermessage_id = build_zerver_usermessage(zerver_usermessage, usermessage_id_count,
                                                       zerver_subscription, recipient_id,
                                                       mentioned_users_id, message_id)
        self.assertEqual(test_usermessage_id, 4)

        self.assertEqual(zerver_usermessage[0]['flags_mask'], 1)
        self.assertEqual(zerver_usermessage[0]['id'], 0)
        self.assertEqual(zerver_usermessage[0]['message'], message_id)
        self.assertEqual(zerver_usermessage[1]['user_profile'],
                         zerver_subscription[2]['user_profile'])
        self.assertEqual(zerver_usermessage[1]['flags_mask'], 9)
        self.assertEqual(zerver_usermessage[3]['id'], 3)
        self.assertEqual(zerver_usermessage[3]['message'], message_id)

    @mock.patch("zerver.lib.slack_data_to_zulip_data.build_zerver_usermessage", return_value = 2)
    def test_channel_message_to_zerver_message(self, mock_build_zerver_usermessage: mock.Mock) -> None:

        user_data = [{"id": "U066MTL5U", "name": "john doe", "deleted": False, "real_name": "John"},
                     {"id": "U061A5N1G", "name": "jane doe", "deleted": False, "real_name": "Jane"},
                     {"id": "U061A1R2R", "name": "jon", "deleted": False, "real_name": "Jon"}]

        added_users = {"U066MTL5U": 5, "U061A5N1G": 24, "U061A1R2R": 43}

        reactions = [{"name": "grinning", "users": ["U061A5N1G"], "count": 1}]

        all_messages = [{"text": "<@U066MTL5U> has joined the channel", "subtype": "channel_join",
                         "user": "U066MTL5U", "ts": "1434139102.000002", "channel_name": "random"},
                        {"text": "<@U061A5N1G>: hey!", "user": "U061A1R2R",
                         "ts": "1437868294.000006", "has_image": True, "channel_name": "random"},
                        {"text": "random", "user": "U061A5N1G", "reactions": reactions,
                         "ts": "1439868294.000006", "channel_name": "random"},
                        {"text": "without a user", "user": None,  # this message will be ignored as it has no user
                         "ts": "1239868294.000006", "channel_name": "general"},
                        {"text": "<http://journals.plos.org/plosone/article>", "user": "U061A1R2R",
                         "ts": "1463868370.000008", "channel_name": "general"},
                        {"text": "test message 2", "user": "U061A5N1G",
                         "ts": "1433868549.000010", "channel_name": "general"},
                        # This message will be ignored since it has no user and file is None.
                        # See #9217 for the situation; likely file uploads on archived channels
                        {'upload': False, 'file': None, 'text': 'A file was shared',
                         'channel_name': 'general', 'type': 'message', 'ts': '1433868549.000011',
                         'subtype': 'file_share'},
                        {"text": "random test", "user": "U061A1R2R",
                         "ts": "1433868669.000012", "channel_name": "general"}]  # type: List[Dict[str, Any]]

        added_recipient = {'random': 2, 'general': 1}

        zerver_usermessage = []  # type: List[Dict[str, Any]]
        zerver_subscription = []  # type: List[Dict[str, Any]]
        added_channels = {'random': ('c5', 1), 'general': ('c6', 2)}  # type: Dict[str, Tuple[str, int]]
        zerver_message, zerver_usermessage, attachment, uploads, \
            reaction = channel_message_to_zerver_message(1, user_data, added_users, added_recipient,
                                                         all_messages, zerver_subscription, [],
                                                         added_channels, 'domain')
        # functioning already tested in helper function
        self.assertEqual(zerver_usermessage, [])
        # subtype: channel_join is filtered
        self.assertEqual(len(zerver_message), 5)

        self.assertEqual(uploads, [])
        self.assertEqual(attachment, [])

        # Test reactions
        self.assertEqual(reaction[0]['user_profile'], 24)
        self.assertEqual(reaction[0]['message'], 1)
        self.assertEqual(reaction[0]['emoji_name'], reactions[0]['name'])

        # Message conversion already tested in tests.test_slack_message_conversion
        self.assertEqual(zerver_message[0]['content'], '@**Jane**: hey!')
        self.assertEqual(zerver_message[0]['has_link'], False)
        self.assertEqual(zerver_message[2]['content'], 'http://journals.plos.org/plosone/article')
        self.assertEqual(zerver_message[2]['has_link'], True)

        self.assertEqual(zerver_message[3]['subject'], 'imported from slack')
        self.assertEqual(zerver_message[4]['recipient'], added_recipient['general'])
        self.assertEqual(zerver_message[2]['subject'], 'imported from slack')
        self.assertEqual(zerver_message[1]['recipient'], added_recipient['random'])

        self.assertEqual(zerver_message[1]['id'], 1)
        self.assertEqual(zerver_message[4]['id'], 4)

        self.assertIsNone(zerver_message[3]['rendered_content'])
        self.assertEqual(zerver_message[0]['has_image'], False)
        self.assertEqual(zerver_message[0]['pub_date'], float(all_messages[1]['ts']))
        self.assertEqual(zerver_message[2]['rendered_content_version'], 1)

        self.assertEqual(zerver_message[0]['sender'], 43)
        self.assertEqual(zerver_message[3]['sender'], 24)

    @mock.patch("zerver.lib.slack_data_to_zulip_data.channel_message_to_zerver_message")
    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_all_messages")
    def test_convert_slack_workspace_messages(self, mock_get_all_messages: mock.Mock,
                                              mock_message: mock.Mock) -> None:
        added_channels = {'random': ('c5', 1), 'general': ('c6', 2)}  # type: Dict[str, Tuple[str, int]]
        zerver_message = [{'id': 1}, {'id': 5}]

        realm = {'zerver_subscription': []}  # type: Dict[str, Any]
        user_list = []  # type: List[Dict[str, Any]]

        zerver_usermessage = [{'id': 3}, {'id': 5}, {'id': 6}, {'id': 9}]

        mock_message.side_effect = [[zerver_message, zerver_usermessage, [], [], []]]
        message_json, uploads, zerver_attachment = convert_slack_workspace_messages(
            './random_path', user_list, 2, {}, {}, added_channels, realm, [], 'domain')
        self.assertEqual(message_json['zerver_message'], zerver_message)
        self.assertEqual(message_json['zerver_usermessage'], zerver_usermessage)

    @mock.patch("zerver.lib.slack_data_to_zulip_data.process_uploads", return_value = [])
    @mock.patch("zerver.lib.slack_data_to_zulip_data.build_zerver_attachment",
                return_value = [])
    @mock.patch("zerver.lib.slack_data_to_zulip_data.build_avatar_url")
    @mock.patch("zerver.lib.slack_data_to_zulip_data.build_avatar")
    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_slack_api_data")
    def test_slack_import_to_existing_database(self, mock_get_slack_api_data: mock.Mock,
                                               mock_build_avatar_url: mock.Mock,
                                               mock_build_avatar: mock.Mock,
                                               mock_process_uploads: mock.Mock,
                                               mock_attachment: mock.Mock) -> None:
        test_slack_dir = os.path.join(settings.DEPLOY_ROOT, "zerver", "fixtures",
                                      "slack_fixtures")
        test_slack_zip_file = os.path.join(test_slack_dir, "test_slack_importer.zip")
        test_slack_unzipped_file = os.path.join(test_slack_dir, "test_slack_importer")

        test_realm_subdomain = 'test-slack-import'
        output_dir = os.path.join(settings.DEPLOY_ROOT, "var", "test-slack-importer-data")
        token = 'valid-token'

        # If the test fails, the 'output_dir' would not be deleted and hence it would give an
        # error when we run the tests next time, as 'do_convert_data' expects an empty 'output_dir'
        # hence we remove it before running 'do_convert_data'
        rm_tree(output_dir)
        # Also the unzipped data file should be removed if the test fails at 'do_convert_data'
        rm_tree(test_slack_unzipped_file)

        user_data_fixture = os.path.join(settings.DEPLOY_ROOT, "zerver", "fixtures",
                                         "slack_fixtures", "user_data.json")
        mock_get_slack_api_data.side_effect = [ujson.load(open(user_data_fixture))['members'], {}]

        do_convert_data(test_slack_zip_file, output_dir, token)
        self.assertTrue(os.path.exists(output_dir))
        self.assertTrue(os.path.exists(output_dir + '/realm.json'))

        # test import of the converted slack data into an existing database
        do_import_realm(output_dir, test_realm_subdomain)
        self.assertTrue(get_realm(test_realm_subdomain).name, test_realm_subdomain)
        Realm.objects.filter(name=test_realm_subdomain).delete()

        remove_folder(output_dir)
        # remove tar file created in 'do_convert_data' function
        os.remove(output_dir + '.tar.gz')
        self.assertFalse(os.path.exists(output_dir))
