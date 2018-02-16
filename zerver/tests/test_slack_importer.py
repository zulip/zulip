# -*- coding: utf-8 -*-
from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.lib.slack_data_to_zulip_data import (
    allocate_ids,
    get_user_data,
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
    get_total_messages_and_usermessages,
    get_message_sending_user,
    build_zerver_usermessage,
    channel_message_to_zerver_message,
    convert_slack_workspace_messages,
    do_convert_data,
)
from zerver.lib.export import (
    do_import_realm,
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
    else:
        return MockResponse(None, 404)

class SlackImporter(ZulipTestCase):
    logger = logging.getLogger()
    # set logger to a higher level to suppress 'logger.INFO' outputs
    logger.setLevel(logging.WARNING)

    def test_allocate_ids(self) -> None:
        start_id_sequence = allocate_ids(Realm, 3)
        self.assertEqual(len(start_id_sequence), 3)

    @mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_get_user_data(self, mock_get: mock.Mock) -> None:
        token = 'valid-token'
        self.assertEqual(get_user_data(token), "user_data")
        token = 'invalid-token'
        with self.assertRaises(Exception) as invalid:
            get_user_data(token)
        self.assertEqual(invalid.exception.args, ('Enter a valid token!',),)

    def test_build_zerver_realm(self) -> None:
        fixtures_path = os.path.dirname(os.path.abspath(__file__)) + '/../fixtures/'
        realm_id = 2
        realm_subdomain = "test-realm"
        time = float(timezone_now().timestamp())
        test_realm = build_zerver_realm(fixtures_path, realm_id, realm_subdomain, time)
        test_zerver_realm_dict = test_realm[0]

        self.assertEqual(test_zerver_realm_dict['id'], realm_id)
        self.assertEqual(test_zerver_realm_dict['string_id'], realm_subdomain)
        self.assertEqual(test_zerver_realm_dict['name'], realm_subdomain)
        self.assertEqual(test_zerver_realm_dict['date_created'], time)

    def test_user_avatars(self) -> None:
        avatar_url = "https://ca.slack-edge.com/{}-{}-{}".format('T5YFFM2QY', 'U6006P1CN',
                                                                 'gd41c3c33cbe')
        self.assertEqual(build_avatar_url('U6006P1CN', 'T5YFFM2QY', 'gd41c3c33cbe'), avatar_url)

        avatar_list = []  # type: List[Dict[str, Any]]
        timestamp = int(timezone_now().timestamp())
        test_avatar_list = build_avatar(1, 1, 'email', avatar_url, timestamp, avatar_list)
        self.assertEqual(test_avatar_list[0]['path'], avatar_url)
        self.assertEqual(test_avatar_list[0]['s3_path'], '')
        self.assertEqual(test_avatar_list[0]['user_profile_id'], 1)

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

    @mock.patch("zerver.lib.slack_data_to_zulip_data.allocate_ids",
                return_value=[1, 2, 3])
    def test_users_to_zerver_userprofile(self, mock_allocate_ids: mock.Mock) -> None:
        user_data = [{"id": "U08RGD1RD",
                      "team_id": "T5YFFM2QY",
                      "name": "john",
                      "deleted": False,
                      "real_name": "John Doe",
                      "profile": {"image_32": "", "email": "jon@gmail.com", "avatar_hash": "hash"}},
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
                                  "email": "jane@foo.com", "avatar_hash": "hash"}},
                     {"id": "U09TYF5Sk",
                      "team_id": "T5YFFM2QY",
                      "name": "Bot",
                      "real_name": "Bot",
                      "is_bot": True,
                      "deleted": False,
                      "profile": {"image_32": "https:\/\/secure.gravatar.com\/avatar\/random1.png",
                                  "email": "bot1@zulipchat.com", "avatar_hash": "hash"}}]

        # As user with slack_id 'U0CBK5KAT' is the primary owner, that user should be imported first
        # and hence has zulip_id = 1
        test_added_users = {'U08RGD1RD': 2,
                            'U0CBK5KAT': 1,
                            'U09TYF5Sk': 3}
        slack_data_dir = './random_path'
        timestamp = int(timezone_now().timestamp())
        zerver_userprofile, added_users = users_to_zerver_userprofile(slack_data_dir, user_data,
                                                                      1, timestamp, 'test_domain')

        # test that the primary owner should always be imported first
        self.assertDictEqual(added_users, test_added_users)

        self.assertEqual(zerver_userprofile[1]['id'], test_added_users['U0CBK5KAT'])
        self.assertEqual(len(zerver_userprofile), 3)
        self.assertEqual(zerver_userprofile[1]['id'], 1)
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
        subscription_id_list = [7, 8, 9, 23]
        recipient_id = 12
        zerver_subscription = []  # type: List[Dict[str, Any]]
        zerver_subscription, final_subscription_id = build_subscription(channel_members,
                                                                        zerver_subscription,
                                                                        recipient_id,
                                                                        added_users,
                                                                        subscription_id_list,
                                                                        subscription_id_count)
        # sanity checks
        self.assertEqual(zerver_subscription[0]['recipient'], 12)
        self.assertEqual(zerver_subscription[0]['id'], 7)
        self.assertEqual(zerver_subscription[0]['user_profile'], added_users[channel_members[0]])
        self.assertEqual(zerver_subscription[2]['user_profile'], added_users[channel_members[2]])
        self.assertEqual(zerver_subscription[3]['id'], 23)
        self.assertEqual(zerver_subscription[1]['recipient'],
                         zerver_subscription[3]['recipient'])
        self.assertEqual(zerver_subscription[1]['pin_to_top'], False)

    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_data_file")
    @mock.patch("zerver.lib.slack_data_to_zulip_data.allocate_ids")
    def test_channels_to_zerver_stream(self, mock_allocate_ids: mock.Mock,
                                       mock_get_data_file: mock.Mock) -> None:

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
        mock_allocate_ids.side_effect = [[1, 2, 3, 4],  # For stream
                                         [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],  # For subscription
                                         [1, 2, 3, 4, 5, 6, 7, 8],  # For recipient
                                         [1, 2]]  # For defaultstream

        channel_to_zerver_stream_output = channels_to_zerver_stream('./random_path', realm_id, added_users,
                                                                    zerver_userprofile)
        zerver_defaultstream = channel_to_zerver_stream_output[0]
        zerver_stream = channel_to_zerver_stream_output[1]
        added_channels = channel_to_zerver_stream_output[2]
        zerver_subscription = channel_to_zerver_stream_output[3]
        zerver_recipient = channel_to_zerver_stream_output[4]
        added_recipient = channel_to_zerver_stream_output[5]

        test_added_channels = {'feedback': 4, 'general': 2, 'general1': 3, 'random': 1}
        test_added_recipient = {'feedback': 4, 'general': 2, 'general1': 3, 'random': 1}

        # zerver defaultstream already tested in helper functions
        self.assertEqual(zerver_defaultstream, [{'id': 1, 'realm': 3, 'stream': 1},
                                                {'id': 2, 'realm': 3, 'stream': 2}])

        self.assertDictEqual(test_added_channels, added_channels)
        self.assertDictEqual(test_added_recipient, added_recipient)

        # functioning of zerver subscriptions are already tested in the helper functions
        # This is to check the concatenation of the output lists from the helper functions
        # subscriptions for stream
        self.assertEqual(zerver_subscription[3]['recipient'], 2)
        self.assertEqual(zerver_subscription[5]['recipient'], 3)
        # subscription for users
        self.assertEqual(zerver_subscription[6]['recipient'], 4)
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
        self.assertEqual(zerver_stream[0]['description'],
                         "topic: {}\npurpose: {}".format('random', 'no purpose'))
        self.assertEqual(zerver_stream[0]['invite_only'], False)
        self.assertEqual(zerver_stream[0]['realm'], realm_id)
        self.assertEqual(zerver_stream[2]['id'],
                         test_added_channels[zerver_stream[2]['name']])

    @mock.patch("zerver.lib.slack_data_to_zulip_data.build_zerver_realm", return_value=[{}])
    @mock.patch("zerver.lib.slack_data_to_zulip_data.users_to_zerver_userprofile",
                return_value=[[], {}])
    @mock.patch("zerver.lib.slack_data_to_zulip_data.channels_to_zerver_stream",
                return_value=[[], [], {}, [], [], {}])
    def test_slack_workspace_to_realm(self, mock_channels_to_zerver_stream: mock.Mock,
                                      mock_users_to_zerver_userprofile: mock.Mock,
                                      mock_build_zerver_realm: mock.Mock) -> None:

        realm_id = 1
        user_list = []  # type: List[Dict[str, Any]]
        with self.settings(EXTERNAL_HOST='testdomain'):
            realm, added_users, added_recipient, added_channels = slack_workspace_to_realm(realm_id,
                                                                                           user_list,
                                                                                           'test-realm',
                                                                                           './fixture',
                                                                                           './random_path')
        test_zerver_realmdomain = [{'realm': realm_id, 'allow_subdomains': False,
                                    'domain': 'testdomain', 'id': realm_id}]
        # Functioning already tests in helper functions
        self.assertEqual(added_users, {})
        self.assertEqual(added_channels, {})
        self.assertEqual(added_recipient, {})

        zerver_realmdomain = realm['zerver_realmdomain']
        self.assertListEqual(zerver_realmdomain, test_zerver_realmdomain)
        self.assertEqual(realm['zerver_userpresence'], [])
        self.assertEqual(realm['zerver_stream'], [])
        self.assertEqual(realm['zerver_userprofile'], [])
        self.assertEqual(realm['zerver_realm'], [{}])

    @mock.patch("os.listdir", return_value = ['2015-08-08.json', '2016-01-15.json'])
    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_data_file")
    def test_get_total_messages_and_usermessages(self, mock_get_data_file: mock.Mock,
                                                 mock_list_dir: mock.Mock) -> None:

        date1 = [{"text": "<@U8VAHEVUY> has joined the channel", "subtype": "channel_join"},
                 {"text": "message"},
                 {"text": "random"},
                 {"text": "test messsage"}]
        date2 = [{"text": "test message 2", "subtype": "channel_leave"},
                 {"text": "random test"},
                 {"text": "message", "subtype": "channel_name"}]
        mock_get_data_file.side_effect = [date1, date2]

        added_recipient = {'random': 2}
        zerver_subscription = [{'recipient': 2}, {'recipient': 4}, {'recipient': 2}]

        total_messages, total_usermessages = get_total_messages_and_usermessages('./path',
                                                                                 'random',
                                                                                 zerver_subscription,
                                                                                 added_recipient)
        # subtype: channel_join, channel_leave are filtered out
        self.assertEqual(total_messages, 4)
        self.assertEqual(total_usermessages, 8)

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
        usermessage_id_list = [3, 7, 8, 11]
        zerver_subscription = [{'recipient': 2, 'user_profile': 7},
                               {'recipient': 4, 'user_profile': 12},
                               {'recipient': 2, 'user_profile': 16},
                               {'recipient': 2, 'user_profile': 15},
                               {'recipient': 2, 'user_profile': 3}]
        recipient_id = 2
        mentioned_users_id = [12, 3, 16]
        message_id = 9

        test_zerver_usermessage, test_usermessage_id = build_zerver_usermessage(zerver_usermessage,
                                                                                usermessage_id_count,
                                                                                usermessage_id_list,
                                                                                zerver_subscription,
                                                                                recipient_id,
                                                                                mentioned_users_id,
                                                                                message_id)
        self.assertEqual(test_usermessage_id, 4)

        self.assertEqual(test_zerver_usermessage[0]['flags_mask'], 1)
        self.assertEqual(test_zerver_usermessage[0]['id'], 3)
        self.assertEqual(test_zerver_usermessage[0]['message'], message_id)
        self.assertEqual(test_zerver_usermessage[1]['user_profile'],
                         zerver_subscription[2]['user_profile'])
        self.assertEqual(test_zerver_usermessage[1]['flags_mask'], 9)
        self.assertEqual(test_zerver_usermessage[3]['id'], 11)
        self.assertEqual(test_zerver_usermessage[3]['message'], message_id)

    @mock.patch("os.listdir", return_value = ['2015-08-08.json', '2016-01-15.json'])
    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_data_file")
    @mock.patch("zerver.lib.slack_data_to_zulip_data.build_zerver_usermessage", return_value = [[], 2])
    def test_channel_message_to_zerver_message(self, mock_build_zerver_usermessage: mock.Mock,
                                               mock_get_data_file: mock.Mock, mock_listdir: mock.Mock) -> None:

        user_data = [{"id": "U066MTL5U", "name": "john doe", "deleted": False, "real_name": "John"},
                     {"id": "U061A5N1G", "name": "jane doe", "deleted": False, "real_name": "Jane"},
                     {"id": "U061A1R2R", "name": "jon", "deleted": False, "real_name": "Jon"}]

        added_users = {"U066MTL5U": 5, "U061A5N1G": 24, "U061A1R2R": 43}

        date1 = [{"text": "<@U066MTL5U> has joined the channel", "subtype": "channel_join",
                  "user": "U066MTL5U", "ts": "1434139102.000002"},
                 {"text": "<@U061A5N1G>: hey!", "user": "U061A1R2R",
                  "ts": "1437868294.000006", "has_image": True},
                 {"text": "random", "user": "U061A5N1G",
                  "ts": "1439868294.000006"},
                 {"text": "without a user", "user": None,  # this message will be ignored as it has no user
                  "ts": "1239868294.000006"},
                 {"text": "<http://journals.plos.org/plosone/article>", "user": "U061A1R2R",
                  "ts": "1463868370.000008"}]  # type: List[Dict[str, Any]]

        date2 = [{"text": "test message 2", "user": "U061A5N1G",
                  "ts": "1433868549.000010"},
                 {"text": "random test", "user": "U061A1R2R",
                  "ts": "1433868669.000012"}]

        mock_get_data_file.side_effect = [date1, date2]
        added_recipient = {'random': 2}
        constants = ['./random_path', 2]
        ids = [0, 0, [3, 4, 5, 6, 7], []]
        channel_name = 'random'

        zerver_usermessage = []  # type: List[Dict[str, Any]]
        zerver_subscription = []  # type: List[Dict[str, Any]]
        zerver_message, zerver_usermessage = channel_message_to_zerver_message(constants, channel_name,
                                                                               user_data, added_users,
                                                                               added_recipient,
                                                                               zerver_subscription, ids)
        # functioning already tested in helper function
        self.assertEqual(zerver_usermessage, [])
        # subtype: channel_join is filtered
        self.assertEqual(len(zerver_message), 5)

        # Message conversion already tested in tests.test_slack_message_conversion
        self.assertEqual(zerver_message[0]['content'], '@**Jane**: hey!')
        self.assertEqual(zerver_message[0]['has_link'], False)
        self.assertEqual(zerver_message[2]['content'], 'http://journals.plos.org/plosone/article')
        self.assertEqual(zerver_message[2]['has_link'], True)

        self.assertEqual(zerver_message[3]['subject'], 'from slack')
        self.assertEqual(zerver_message[4]['recipient'], added_recipient[channel_name])
        self.assertEqual(zerver_message[2]['subject'], 'from slack')
        self.assertEqual(zerver_message[1]['recipient'], added_recipient[channel_name])

        self.assertEqual(zerver_message[1]['id'], 4)
        self.assertEqual(zerver_message[4]['id'], 7)

        self.assertIsNone(zerver_message[3]['rendered_content'])
        self.assertEqual(zerver_message[0]['has_image'], date1[1]['has_image'])
        self.assertEqual(zerver_message[0]['pub_date'], float(date1[1]['ts']))
        self.assertEqual(zerver_message[2]['rendered_content_version'], 1)

        self.assertEqual(zerver_message[0]['sender'], 43)
        self.assertEqual(zerver_message[3]['sender'], 24)

    @mock.patch("zerver.lib.slack_data_to_zulip_data.channel_message_to_zerver_message")
    @mock.patch("zerver.lib.slack_data_to_zulip_data.allocate_ids")
    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_total_messages_and_usermessages", return_value=[1, 2])
    def test_convert_slack_workspace_messages(self, mock_get_total_messages_and_usermessages: mock.Mock,
                                              mock_allocate_ids: mock.Mock, mock_message: mock.Mock) -> None:
        added_channels = {'random': 1, 'general': 2}

        zerver_message1 = [{'id': 1}]
        zerver_message2 = [{'id': 5}]

        realm = {'zerver_subscription': []}  # type: Dict[str, Any]
        user_list = []  # type: List[Dict[str, Any]]

        zerver_usermessage1 = [{'id': 3}, {'id': 5}]
        zerver_usermessage2 = [{'id': 6}, {'id': 9}]

        mock_message.side_effect = [[zerver_message1, zerver_usermessage1],
                                    [zerver_message2, zerver_usermessage2]]
        message_json = convert_slack_workspace_messages('./random_path', user_list, 2, {},
                                                        {}, added_channels,
                                                        realm)
        self.assertEqual(message_json['zerver_message'], zerver_message1 + zerver_message2)
        self.assertEqual(message_json['zerver_usermessage'], zerver_usermessage1 + zerver_usermessage2)

    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_user_data")
    def test_slack_import_to_existing_database(self, mock_get_user_data: mock.Mock) -> None:
        test_slack_zip_file = os.path.join(settings.DEPLOY_ROOT, "zerver", "fixtures",
                                           "slack_fixtures", "test_slack_importer.zip")
        test_realm_subdomain = 'test-slack-import'
        output_dir = '/tmp/test-slack-importer-data'
        token = 'valid-token'

        user_data_fixture = os.path.join(settings.DEPLOY_ROOT, "zerver", "fixtures",
                                         "slack_fixtures", "user_data.json")
        mock_get_user_data.return_value = ujson.load(open(user_data_fixture))['members']

        do_convert_data(test_slack_zip_file, test_realm_subdomain, output_dir, token)
        self.assertTrue(os.path.exists(output_dir))
        self.assertTrue(os.path.exists(output_dir + '/realm.json'))

        # test import of the converted slack data into an existing database
        do_import_realm(output_dir)
        self.assertTrue(get_realm(test_realm_subdomain).name, test_realm_subdomain)
        Realm.objects.filter(name=test_realm_subdomain).delete()

        remove_folder(output_dir)
        # remove tar file created in 'do_convert_data' function
        os.remove(output_dir + '.tar.gz')
        self.assertFalse(os.path.exists(output_dir))
