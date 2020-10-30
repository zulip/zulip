import datetime
from operator import itemgetter
from typing import Any, Dict, List, Tuple
from unittest import mock

import orjson
from django.db import IntegrityError
from django.http import HttpResponse

from zerver.lib.actions import (
    do_set_realm_property,
    do_update_message,
    get_topic_messages,
    get_user_info_for_message_updates,
)
from zerver.lib.message import MessageDict, has_message_access, messages_for_ids
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import queries_captured
from zerver.lib.topic import LEGACY_PREV_TOPIC, TOPIC_NAME
from zerver.models import Message, Stream, UserMessage, UserProfile


class EditMessageTest(ZulipTestCase):
    def check_topic(self,
                    msg_id: int,
                    topic_name: str) -> None:
        msg = Message.objects.get(id=msg_id)
        self.assertEqual(msg.topic_name(), topic_name)

    def check_message(self,
                      msg_id: int,
                      topic_name: str,
                      content: str) -> None:
        # Make sure we saved the message correctly to the DB.
        msg = Message.objects.get(id=msg_id)
        self.assertEqual(msg.topic_name(), topic_name)
        self.assertEqual(msg.content, content)

        '''
        Next, we will make sure we properly cached the
        messages.  We still have to do 2 queries to
        hydrate sender/recipient info, but we won't need
        to hit the zerver_message table.
        '''

        with queries_captured() as queries:
            (fetch_message_dict,) = messages_for_ids(
                message_ids = [msg.id],
                user_message_flags={msg_id: []},
                search_fields={},
                apply_markdown=False,
                client_gravatar=False,
                allow_edit_history=True,
            )

        self.assertEqual(len(queries), 2)
        for query in queries:
            self.assertNotIn('message', query['sql'])

        self.assertEqual(
            fetch_message_dict[TOPIC_NAME],
            msg.topic_name(),
        )
        self.assertEqual(
            fetch_message_dict['content'],
            msg.content,
        )
        self.assertEqual(
            fetch_message_dict['sender_id'],
            msg.sender_id,
        )

        if msg.edit_history:
            self.assertEqual(
                fetch_message_dict['edit_history'],
                orjson.loads(msg.edit_history),
            )

    def test_query_count_on_to_dict_uncached(self) -> None:
        # `to_dict_uncached` method is used by the mechanisms
        # tested in this class. Hence, its performance is tested here.
        # Generate 2 messages
        user = self.example_user("hamlet")
        self.login_user(user)
        stream_name = "public_stream"
        self.subscribe(user, stream_name)
        message_ids = []
        message_ids.append(self.send_stream_message(user,
                                                    stream_name, "Message one"))
        user_2 = self.example_user("cordelia")
        self.subscribe(user_2, stream_name)
        message_ids.append(self.send_stream_message(user_2,
                                                    stream_name, "Message two"))
        self.subscribe(self.notification_bot(), stream_name)
        message_ids.append(self.send_stream_message(self.notification_bot(),
                                                    stream_name, "Message three"))
        messages = [Message.objects.select_related().get(id=message_id)
                    for message_id in message_ids]

        # Check number of queries performed
        with queries_captured() as queries:
            MessageDict.to_dict_uncached(messages)
        # 1 query for realm_id per message = 3
        # 1 query each for reactions & submessage for all messages = 2
        self.assertEqual(len(queries), 5)

        realm_id = 2  # Fetched from stream object
        # Check number of queries performed with realm_id
        with queries_captured() as queries:
            MessageDict.to_dict_uncached(messages, realm_id)
        # 1 query each for reactions & submessage for all messages = 2
        self.assertEqual(len(queries), 2)

    def test_save_message(self) -> None:
        """This is also tested by a client test, but here we can verify
        the cache against the database"""
        self.login('hamlet')
        msg_id = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                          topic_name="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': 'after edit',
        })
        self.assert_json_success(result)
        self.check_message(msg_id, topic_name="editing", content="after edit")

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'topic': 'edited',
        })
        self.assert_json_success(result)
        self.check_topic(msg_id, topic_name="edited")

    def test_fetch_raw_message(self) -> None:
        self.login('hamlet')
        msg_id = self.send_personal_message(
            from_user=self.example_user("hamlet"),
            to_user=self.example_user("cordelia"),
            content="**before** edit",
        )
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_success(result)
        self.assertEqual(result.json()['raw_content'], '**before** edit')

        # Test error cases
        result = self.client_get('/json/messages/999999')
        self.assert_json_error(result, 'Invalid message(s)')

        self.login('cordelia')
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_success(result)

        self.login('othello')
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_error(result, 'Invalid message(s)')

    def test_fetch_raw_message_stream_wrong_realm(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        stream = self.make_stream('public_stream')
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_stream_message(user_profile, stream.name,
                                          topic_name="test", content="test")
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_success(result)

        mit_user = self.mit_user('sipbtest')
        self.login_user(mit_user)
        result = self.client_get('/json/messages/' + str(msg_id), subdomain="zephyr")
        self.assert_json_error(result, 'Invalid message(s)')

    def test_fetch_raw_message_private_stream(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        stream = self.make_stream('private_stream', invite_only=True)
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_stream_message(user_profile, stream.name,
                                          topic_name="test", content="test")
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_success(result)
        self.login('othello')
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_error(result, 'Invalid message(s)')

    def test_edit_message_no_permission(self) -> None:
        self.login('hamlet')
        msg_id = self.send_stream_message(self.example_user("iago"), "Scotland",
                                          topic_name="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': 'content after edit',
        })
        self.assert_json_error(result, "You don't have permission to edit this message")

    def test_edit_message_no_changes(self) -> None:
        self.login('hamlet')
        msg_id = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                          topic_name="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
        })
        self.assert_json_error(result, "Nothing to change")

    def test_edit_message_no_topic(self) -> None:
        self.login('hamlet')
        msg_id = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                          topic_name="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'topic': ' ',
        })
        self.assert_json_error(result, "Topic can't be empty")

    def test_edit_message_no_content(self) -> None:
        self.login('hamlet')
        msg_id = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                          topic_name="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': ' ',
        })
        self.assert_json_success(result)
        content = Message.objects.filter(id=msg_id).values_list('content', flat = True)[0]
        self.assertEqual(content, "(deleted)")

    def test_edit_message_history_disabled(self) -> None:
        user_profile = self.example_user("hamlet")
        do_set_realm_property(user_profile.realm, "allow_edit_history", False)
        self.login('hamlet')

        # Single-line edit
        msg_id_1 = self.send_stream_message(self.example_user("hamlet"),
                                            "Denmark",
                                            topic_name="editing",
                                            content="content before edit")

        new_content_1 = 'content after edit'
        result_1 = self.client_patch("/json/messages/" + str(msg_id_1), {
            'message_id': msg_id_1, 'content': new_content_1,
        })
        self.assert_json_success(result_1)

        result = self.client_get(
            "/json/messages/" + str(msg_id_1) + "/history")
        self.assert_json_error(result, "Message edit history is disabled in this organization")

        # Now verify that if we fetch the message directly, there's no
        # edit history data attached.
        messages_result = self.client_get("/json/messages",
                                          {"anchor": msg_id_1, "num_before": 0, "num_after": 10})
        self.assert_json_success(messages_result)
        json_messages = orjson.loads(messages_result.content)
        for msg in json_messages['messages']:
            self.assertNotIn("edit_history", msg)

    def test_edit_message_history(self) -> None:
        self.login('hamlet')

        # Single-line edit
        msg_id_1 = self.send_stream_message(
            self.example_user("hamlet"),
            "Scotland",
            topic_name="editing",
            content="content before edit")
        new_content_1 = 'content after edit'
        result_1 = self.client_patch("/json/messages/" + str(msg_id_1), {
            'message_id': msg_id_1, 'content': new_content_1,
        })
        self.assert_json_success(result_1)

        message_edit_history_1 = self.client_get(
            "/json/messages/" + str(msg_id_1) + "/history")
        json_response_1 = orjson.loads(message_edit_history_1.content)
        message_history_1 = json_response_1['message_history']

        # Check content of message after edit.
        self.assertEqual(message_history_1[0]['rendered_content'],
                         '<p>content before edit</p>')
        self.assertEqual(message_history_1[1]['rendered_content'],
                         '<p>content after edit</p>')
        self.assertEqual(message_history_1[1]['content_html_diff'],
                         ('<p>content '
                          '<span class="highlight_text_inserted">after</span> '
                          '<span class="highlight_text_deleted">before</span>'
                          ' edit</p>'))
        # Check content of message before edit.
        self.assertEqual(message_history_1[1]['prev_rendered_content'],
                         '<p>content before edit</p>')

        # Edits on new lines
        msg_id_2 = self.send_stream_message(
            self.example_user("hamlet"),
            "Scotland",
            topic_name="editing",
            content=('content before edit, line 1\n'
                     '\n'
                     'content before edit, line 3'))
        new_content_2 = ('content before edit, line 1\n'
                         'content after edit, line 2\n'
                         'content before edit, line 3')
        result_2 = self.client_patch("/json/messages/" + str(msg_id_2), {
            'message_id': msg_id_2, 'content': new_content_2,
        })
        self.assert_json_success(result_2)

        message_edit_history_2 = self.client_get(
            "/json/messages/" + str(msg_id_2) + "/history")
        json_response_2 = orjson.loads(message_edit_history_2.content)
        message_history_2 = json_response_2['message_history']

        self.assertEqual(message_history_2[0]['rendered_content'],
                         ('<p>content before edit, line 1</p>\n'
                          '<p>content before edit, line 3</p>'))
        self.assertEqual(message_history_2[1]['rendered_content'],
                         ('<p>content before edit, line 1<br>\n'
                          'content after edit, line 2<br>\n'
                          'content before edit, line 3</p>'))
        self.assertEqual(message_history_2[1]['content_html_diff'],
                         ('<p>content before edit, line 1<br> '
                          'content <span class="highlight_text_inserted">after edit, line 2<br> '
                          'content</span> before edit, line 3</p>'))
        self.assertEqual(message_history_2[1]['prev_rendered_content'],
                         ('<p>content before edit, line 1</p>\n'
                          '<p>content before edit, line 3</p>'))

    def test_edit_link(self) -> None:
        # Link editing
        self.login('hamlet')
        msg_id_1 = self.send_stream_message(
            self.example_user("hamlet"),
            "Scotland",
            topic_name="editing",
            content="Here is a link to [zulip](www.zulip.org).")
        new_content_1 = 'Here is a link to [zulip](www.zulipchat.com).'
        result_1 = self.client_patch("/json/messages/" + str(msg_id_1), {
            'message_id': msg_id_1, 'content': new_content_1,
        })
        self.assert_json_success(result_1)

        message_edit_history_1 = self.client_get(
            "/json/messages/" + str(msg_id_1) + "/history")
        json_response_1 = orjson.loads(message_edit_history_1.content)
        message_history_1 = json_response_1['message_history']

        # Check content of message after edit.
        self.assertEqual(message_history_1[0]['rendered_content'],
                         '<p>Here is a link to '
                         '<a href="http://www.zulip.org">zulip</a>.</p>')
        self.assertEqual(message_history_1[1]['rendered_content'],
                         '<p>Here is a link to '
                         '<a href="http://www.zulipchat.com">zulip</a>.</p>')
        self.assertEqual(message_history_1[1]['content_html_diff'],
                         ('<p>Here is a link to <a href="http://www.zulipchat.com"'
                          '>zulip '
                          '<span class="highlight_text_inserted"> Link: http://www.zulipchat.com .'
                          '</span> <span class="highlight_text_deleted"> Link: http://www.zulip.org .'
                          '</span> </a></p>'))

    def test_edit_history_unedited(self) -> None:
        self.login('hamlet')

        msg_id = self.send_stream_message(
            self.example_user('hamlet'),
            'Scotland',
            topic_name='editing',
            content='This message has not been edited.')

        result = self.client_get(f'/json/messages/{msg_id}/history')

        self.assert_json_success(result)

        message_history = result.json()['message_history']
        self.assert_length(message_history, 1)

    def test_user_info_for_updates(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')

        self.login_user(hamlet)
        self.subscribe(hamlet, 'Scotland')
        self.subscribe(cordelia, 'Scotland')

        msg_id = self.send_stream_message(hamlet, 'Scotland',
                                          content='@**Cordelia Lear**')

        user_info = get_user_info_for_message_updates(msg_id)
        message_user_ids = user_info['message_user_ids']
        self.assertIn(hamlet.id, message_user_ids)
        self.assertIn(cordelia.id, message_user_ids)

        mention_user_ids = user_info['mention_user_ids']
        self.assertEqual(mention_user_ids, {cordelia.id})

    def test_edit_cases(self) -> None:
        """This test verifies the accuracy of construction of Zulip's edit
        history data structures."""
        self.login('hamlet')
        hamlet = self.example_user('hamlet')
        msg_id = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                          topic_name="topic 1", content="content 1")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': 'content 2',
        })
        self.assert_json_success(result)
        history = orjson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0]['prev_content'], 'content 1')
        self.assertEqual(history[0]['user_id'], hamlet.id)
        self.assertEqual(set(history[0].keys()),
                         {'timestamp', 'prev_content', 'user_id',
                          'prev_rendered_content', 'prev_rendered_content_version'})

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'topic': 'topic 2',
        })
        self.assert_json_success(result)
        history = orjson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0][LEGACY_PREV_TOPIC], 'topic 1')
        self.assertEqual(history[0]['user_id'], hamlet.id)
        self.assertEqual(set(history[0].keys()), {'timestamp', LEGACY_PREV_TOPIC, 'user_id'})

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': 'content 3',
            'topic': 'topic 3',
        })
        self.assert_json_success(result)
        history = orjson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0]['prev_content'], 'content 2')
        self.assertEqual(history[0][LEGACY_PREV_TOPIC], 'topic 2')
        self.assertEqual(history[0]['user_id'], hamlet.id)
        self.assertEqual(set(history[0].keys()),
                         {'timestamp', LEGACY_PREV_TOPIC, 'prev_content', 'user_id',
                          'prev_rendered_content', 'prev_rendered_content_version'})

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': 'content 4',
        })
        self.assert_json_success(result)
        history = orjson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0]['prev_content'], 'content 3')
        self.assertEqual(history[0]['user_id'], hamlet.id)

        self.login('iago')
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'topic': 'topic 4',
        })
        self.assert_json_success(result)
        history = orjson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0][LEGACY_PREV_TOPIC], 'topic 3')
        self.assertEqual(history[0]['user_id'], self.example_user('iago').id)

        history = orjson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0][LEGACY_PREV_TOPIC], 'topic 3')
        self.assertEqual(history[2][LEGACY_PREV_TOPIC], 'topic 2')
        self.assertEqual(history[3][LEGACY_PREV_TOPIC], 'topic 1')
        self.assertEqual(history[1]['prev_content'], 'content 3')
        self.assertEqual(history[2]['prev_content'], 'content 2')
        self.assertEqual(history[4]['prev_content'], 'content 1')

        # Now, we verify that the edit history data sent back has the
        # correct filled-out fields
        message_edit_history = self.client_get("/json/messages/" + str(msg_id) + "/history")

        json_response = orjson.loads(message_edit_history.content)

        # We reverse the message history view output so that the IDs line up with the above.
        message_history = list(reversed(json_response['message_history']))
        i = 0
        for entry in message_history:
            expected_entries = {'content', 'rendered_content', 'topic', 'timestamp', 'user_id'}
            if i in {0, 2, 3}:
                expected_entries.add('prev_topic')
            if i in {1, 2, 4}:
                expected_entries.add('prev_content')
                expected_entries.add('prev_rendered_content')
                expected_entries.add('content_html_diff')
            i += 1
            self.assertEqual(expected_entries, set(entry.keys()))
        self.assertEqual(len(message_history), 6)
        self.assertEqual(message_history[0]['prev_topic'], 'topic 3')
        self.assertEqual(message_history[0]['topic'], 'topic 4')
        self.assertEqual(message_history[1]['topic'], 'topic 3')
        self.assertEqual(message_history[2]['topic'], 'topic 3')
        self.assertEqual(message_history[2]['prev_topic'], 'topic 2')
        self.assertEqual(message_history[3]['topic'], 'topic 2')
        self.assertEqual(message_history[3]['prev_topic'], 'topic 1')
        self.assertEqual(message_history[4]['topic'], 'topic 1')

        self.assertEqual(message_history[0]['content'], 'content 4')
        self.assertEqual(message_history[1]['content'], 'content 4')
        self.assertEqual(message_history[1]['prev_content'], 'content 3')
        self.assertEqual(message_history[2]['content'], 'content 3')
        self.assertEqual(message_history[2]['prev_content'], 'content 2')
        self.assertEqual(message_history[3]['content'], 'content 2')
        self.assertEqual(message_history[4]['content'], 'content 2')
        self.assertEqual(message_history[4]['prev_content'], 'content 1')

        self.assertEqual(message_history[5]['content'], 'content 1')
        self.assertEqual(message_history[5]['topic'], 'topic 1')

    def test_edit_message_content_limit(self) -> None:
        def set_message_editing_params(allow_message_editing: bool,
                                       message_content_edit_limit_seconds: int,
                                       allow_community_topic_editing: bool) -> None:
            result = self.client_patch("/json/realm", {
                'allow_message_editing': orjson.dumps(allow_message_editing).decode(),
                'message_content_edit_limit_seconds': message_content_edit_limit_seconds,
                'allow_community_topic_editing': orjson.dumps(allow_community_topic_editing).decode(),
            })
            self.assert_json_success(result)

        def do_edit_message_assert_success(id_: int, unique_str: str, topic_only: bool=False) -> None:
            new_topic = 'topic' + unique_str
            new_content = 'content' + unique_str
            params_dict = {'message_id': id_, 'topic': new_topic}
            if not topic_only:
                params_dict['content'] = new_content
            result = self.client_patch("/json/messages/" + str(id_), params_dict)
            self.assert_json_success(result)
            if topic_only:
                self.check_topic(id_, topic_name=new_topic)
            else:
                self.check_message(id_, topic_name=new_topic, content=new_content)

        def do_edit_message_assert_error(id_: int, unique_str: str, error: str,
                                         topic_only: bool=False) -> None:
            message = Message.objects.get(id=id_)
            old_topic = message.topic_name()
            old_content = message.content
            new_topic = 'topic' + unique_str
            new_content = 'content' + unique_str
            params_dict = {'message_id': id_, 'topic': new_topic}
            if not topic_only:
                params_dict['content'] = new_content
            result = self.client_patch("/json/messages/" + str(id_), params_dict)
            message = Message.objects.get(id=id_)
            self.assert_json_error(result, error)

            msg = Message.objects.get(id=id_)
            self.assertEqual(msg.topic_name(), old_topic)
            self.assertEqual(msg.content, old_content)

        self.login('iago')
        # send a message in the past
        id_ = self.send_stream_message(self.example_user("iago"), "Scotland",
                                       content="content", topic_name="topic")
        message = Message.objects.get(id=id_)
        message.date_sent = message.date_sent - datetime.timedelta(seconds=180)
        message.save()

        # test the various possible message editing settings
        # high enough time limit, all edits allowed
        set_message_editing_params(True, 240, False)
        do_edit_message_assert_success(id_, 'A')

        # out of time, only topic editing allowed
        set_message_editing_params(True, 120, False)
        do_edit_message_assert_success(id_, 'B', True)
        do_edit_message_assert_error(id_, 'C', "The time limit for editing this message has passed")

        # infinite time, all edits allowed
        set_message_editing_params(True, 0, False)
        do_edit_message_assert_success(id_, 'D')

        # without allow_message_editing, nothing is allowed
        set_message_editing_params(False, 240, False)
        do_edit_message_assert_error(id_, 'E', "Your organization has turned off message editing", True)
        set_message_editing_params(False, 120, False)
        do_edit_message_assert_error(id_, 'F', "Your organization has turned off message editing", True)
        set_message_editing_params(False, 0, False)
        do_edit_message_assert_error(id_, 'G', "Your organization has turned off message editing", True)

    def test_allow_community_topic_editing(self) -> None:
        def set_message_editing_params(allow_message_editing: bool,
                                       message_content_edit_limit_seconds: int,
                                       allow_community_topic_editing: bool) -> None:
            result = self.client_patch("/json/realm", {
                'allow_message_editing': orjson.dumps(allow_message_editing).decode(),
                'message_content_edit_limit_seconds': message_content_edit_limit_seconds,
                'allow_community_topic_editing': orjson.dumps(allow_community_topic_editing).decode(),
            })
            self.assert_json_success(result)

        def do_edit_message_assert_success(id_: int, unique_str: str) -> None:
            new_topic = 'topic' + unique_str
            params_dict = {'message_id': id_, 'topic': new_topic}
            result = self.client_patch("/json/messages/" + str(id_), params_dict)
            self.assert_json_success(result)
            self.check_topic(id_, topic_name=new_topic)

        def do_edit_message_assert_error(id_: int, unique_str: str, error: str) -> None:
            message = Message.objects.get(id=id_)
            old_topic = message.topic_name()
            old_content = message.content
            new_topic = 'topic' + unique_str
            params_dict = {'message_id': id_, 'topic': new_topic}
            result = self.client_patch("/json/messages/" + str(id_), params_dict)
            message = Message.objects.get(id=id_)
            self.assert_json_error(result, error)
            msg = Message.objects.get(id=id_)
            self.assertEqual(msg.topic_name(), old_topic)
            self.assertEqual(msg.content, old_content)

        self.login('iago')
        # send a message in the past
        id_ = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                       content="content", topic_name="topic")
        message = Message.objects.get(id=id_)
        message.date_sent = message.date_sent - datetime.timedelta(seconds=180)
        message.save()

        # any user can edit the topic of a message
        set_message_editing_params(True, 0, True)
        # log in as a new user
        self.login('cordelia')
        do_edit_message_assert_success(id_, 'A')

        # only admins can edit the topics of messages
        self.login('iago')
        set_message_editing_params(True, 0, False)
        do_edit_message_assert_success(id_, 'B')
        self.login('cordelia')
        do_edit_message_assert_error(id_, 'C', "You don't have permission to edit this message")

        # users cannot edit topics if allow_message_editing is False
        self.login('iago')
        set_message_editing_params(False, 0, True)
        self.login('cordelia')
        do_edit_message_assert_error(id_, 'D', "Your organization has turned off message editing")

        # non-admin users cannot edit topics sent > 24 hrs ago
        message.date_sent = message.date_sent - datetime.timedelta(seconds=90000)
        message.save()
        self.login('iago')
        set_message_editing_params(True, 0, True)
        do_edit_message_assert_success(id_, 'E')
        self.login('cordelia')
        do_edit_message_assert_error(id_, 'F', "The time limit for editing this message has passed")

        # anyone should be able to edit "no topic" indefinitely
        message.set_topic_name("(no topic)")
        message.save()
        self.login('cordelia')
        do_edit_message_assert_success(id_, 'D')

    @mock.patch("zerver.lib.actions.send_event")
    def test_edit_topic_public_history_stream(self, mock_send_event: mock.MagicMock) -> None:
        stream_name = "Macbeth"
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.make_stream(stream_name, history_public_to_subscribers=True)
        self.subscribe(hamlet, stream_name)
        self.login_user(hamlet)
        message_id = self.send_stream_message(hamlet, stream_name, "Where am I?")

        self.login_user(cordelia)
        self.subscribe(cordelia, stream_name)
        message = Message.objects.get(id=message_id)

        def do_update_message_topic_success(user_profile: UserProfile, message: Message,
                                            topic_name: str, users_to_be_notified: List[Dict[str, Any]]) -> None:
            do_update_message(
                user_profile=user_profile,
                message=message,
                new_stream=None,
                topic_name=topic_name,
                propagate_mode="change_later",
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                content=None,
                rendered_content=None,
                prior_mention_user_ids=set(),
                mention_user_ids=set(),
                mention_data=None,
            )

            mock_send_event.assert_called_with(mock.ANY, mock.ANY, users_to_be_notified)

        # Returns the users that need to be notified when a message topic is changed
        def notify(user_id: int) -> Dict[str, Any]:
            um = UserMessage.objects.get(message=message_id)
            if um.user_profile_id == user_id:
                return {
                    "id": user_id,
                    "flags": um.flags_list(),
                }

            else:
                return {
                    "id": user_id,
                    "flags": ["read"],
                }

        users_to_be_notified = list(map(notify, [hamlet.id, cordelia.id]))
        # Edit topic of a message sent before Cordelia subscribed the stream
        do_update_message_topic_success(cordelia, message, "Othello eats apple", users_to_be_notified)

        # If Cordelia is long-term idle, she doesn't get a notification.
        cordelia.long_term_idle = True
        cordelia.save()
        users_to_be_notified = list(map(notify, [hamlet.id]))
        do_update_message_topic_success(cordelia, message, "Another topic idle", users_to_be_notified)
        cordelia.long_term_idle = False
        cordelia.save()

        # Even if Hamlet unsubscribes the stream, he should be notified when the topic is changed
        # because he has a UserMessage row.
        self.unsubscribe(hamlet, stream_name)
        users_to_be_notified = list(map(notify, [hamlet.id, cordelia.id]))
        do_update_message_topic_success(cordelia, message, "Another topic", users_to_be_notified)

        # Hamlet subscribes to the stream again and Cordelia unsubscribes, then Hamlet changes
        # the message topic. Cordelia won't receive any updates when a message on that stream is
        # changed because she is not a subscriber and doesn't have a UserMessage row.
        self.subscribe(hamlet, stream_name)
        self.unsubscribe(cordelia, stream_name)
        self.login_user(hamlet)
        users_to_be_notified = list(map(notify, [hamlet.id]))
        do_update_message_topic_success(hamlet, message, "Change again", users_to_be_notified)

    @mock.patch("zerver.lib.actions.send_event")
    def test_wildcard_mention(self, mock_send_event: mock.MagicMock) -> None:
        stream_name = "Macbeth"
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.make_stream(stream_name, history_public_to_subscribers=True)
        self.subscribe(hamlet, stream_name)
        self.subscribe(cordelia, stream_name)
        self.login_user(hamlet)
        message_id = self.send_stream_message(hamlet, stream_name, "Hello everyone")

        def notify(user_id: int) -> Dict[str, Any]:
            return {
                "id": user_id,
                "flags": ["wildcard_mentioned"],
            }

        users_to_be_notified = sorted(map(notify, [cordelia.id, hamlet.id]), key=itemgetter("id"))
        result = self.client_patch("/json/messages/" + str(message_id), {
            'message_id': message_id,
            'content': 'Hello @**everyone**',
        })
        self.assert_json_success(result)

        # Extract the send_event call where event type is 'update_message'.
        # Here we assert wildcard_mention_user_ids has been set properly.
        called = False
        for call_args in mock_send_event.call_args_list:
            (arg_realm, arg_event, arg_notified_users) = call_args[0]
            if arg_event['type'] == 'update_message':
                self.assertEqual(arg_event['type'], 'update_message')
                self.assertEqual(arg_event['wildcard_mention_user_ids'], [cordelia.id, hamlet.id])
                self.assertEqual(sorted(arg_notified_users, key=itemgetter("id")), users_to_be_notified)
                called = True
        self.assertTrue(called)

    def test_propagate_topic_forward(self) -> None:
        self.login('hamlet')
        id1 = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                       topic_name="topic1")
        id2 = self.send_stream_message(self.example_user("iago"), "Scotland",
                                       topic_name="topic1")
        id3 = self.send_stream_message(self.example_user("iago"), "Rome",
                                       topic_name="topic1")
        id4 = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                       topic_name="topic2")
        id5 = self.send_stream_message(self.example_user("iago"), "Scotland",
                                       topic_name="topic1")

        result = self.client_patch("/json/messages/" + str(id1), {
            'message_id': id1,
            'topic': 'edited',
            'propagate_mode': 'change_later',
        })
        self.assert_json_success(result)

        self.check_topic(id1, topic_name="edited")
        self.check_topic(id2, topic_name="edited")
        self.check_topic(id3, topic_name="topic1")
        self.check_topic(id4, topic_name="topic2")
        self.check_topic(id5, topic_name="edited")

    def test_propagate_all_topics(self) -> None:
        self.login('hamlet')
        id1 = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                       topic_name="topic1")
        id2 = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                       topic_name="topic1")
        id3 = self.send_stream_message(self.example_user("iago"), "Rome",
                                       topic_name="topic1")
        id4 = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                       topic_name="topic2")
        id5 = self.send_stream_message(self.example_user("iago"), "Scotland",
                                       topic_name="topic1")
        id6 = self.send_stream_message(self.example_user("iago"), "Scotland",
                                       topic_name="topic3")

        result = self.client_patch("/json/messages/" + str(id2), {
            'message_id': id2,
            'topic': 'edited',
            'propagate_mode': 'change_all',
        })
        self.assert_json_success(result)

        self.check_topic(id1, topic_name="edited")
        self.check_topic(id2, topic_name="edited")
        self.check_topic(id3, topic_name="topic1")
        self.check_topic(id4, topic_name="topic2")
        self.check_topic(id5, topic_name="edited")
        self.check_topic(id6, topic_name="topic3")

    def test_propagate_all_topics_with_different_uppercase_letters(self) -> None:
        self.login('hamlet')
        id1 = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                       topic_name="topic1")
        id2 = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                       topic_name="Topic1")
        id3 = self.send_stream_message(self.example_user("iago"), "Rome",
                                       topic_name="topiC1")
        id4 = self.send_stream_message(self.example_user("iago"), "Scotland",
                                       topic_name="toPic1")

        result = self.client_patch("/json/messages/" + str(id2), {
            'message_id': id2,
            'topic': 'edited',
            'propagate_mode': 'change_all',
        })
        self.assert_json_success(result)

        self.check_topic(id1, topic_name="edited")
        self.check_topic(id2, topic_name="edited")
        self.check_topic(id3, topic_name="topiC1")
        self.check_topic(id4, topic_name="edited")

    def test_propagate_invalid(self) -> None:
        self.login('hamlet')
        id1 = self.send_stream_message(self.example_user("hamlet"), "Scotland",
                                       topic_name="topic1")

        result = self.client_patch("/json/messages/" + str(id1), {
            'topic': 'edited',
            'propagate_mode': 'invalid',
        })
        self.assert_json_error(result, 'Invalid propagate_mode')
        self.check_topic(id1, topic_name="topic1")

        result = self.client_patch("/json/messages/" + str(id1), {
            'content': 'edited',
            'propagate_mode': 'change_all',
        })
        self.assert_json_error(result, 'Invalid propagate_mode without topic edit')
        self.check_topic(id1, topic_name="topic1")

    def prepare_move_topics(self, user_email: str, old_stream: str, new_stream: str, topic: str) -> Tuple[UserProfile, Stream, Stream, int, int]:
        user_profile = self.example_user(user_email)
        self.login(user_email)
        stream = self.make_stream(old_stream)
        new_stream = self.make_stream(new_stream)
        self.subscribe(user_profile, stream.name)
        self.subscribe(user_profile, new_stream.name)
        msg_id = self.send_stream_message(user_profile, stream.name,
                                          topic_name=topic, content="First")
        msg_id_lt = self.send_stream_message(user_profile, stream.name,
                                             topic_name=topic, content="Second")

        self.send_stream_message(user_profile, stream.name,
                                 topic_name=topic, content="third")

        return (user_profile, stream, new_stream, msg_id, msg_id_lt)

    def test_move_message_to_stream(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_lt) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test")

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'stream_id': new_stream.id,
            'propagate_mode': 'change_all',
        })

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].content, f"This topic was moved by @_**Iago|{user_profile.id}** to #**new stream>test**")

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[3].content, f"This topic was moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**")

    def test_move_message_to_stream_change_later(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test")

        result = self.client_patch("/json/messages/" + str(msg_id_later), {
            'message_id': msg_id_later,
            'stream_id': new_stream.id,
            'propagate_mode': 'change_later',
        })
        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].id, msg_id)
        self.assertEqual(messages[1].content, f"This topic was moved by @_**Iago|{user_profile.id}** to #**new stream>test**")

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0].id, msg_id_later)
        self.assertEqual(messages[2].content, f"This topic was moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**")

    def test_move_message_to_stream_no_allowed(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "aaron", "test move stream", "new stream", "test")

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'stream_id': new_stream.id,
            'propagate_mode': 'change_all',
        })
        self.assert_json_error(result, "You don't have permission to move this message")

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assertEqual(len(messages), 3)

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assertEqual(len(messages), 0)

    def test_move_message_to_stream_with_content(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test")

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'stream_id': new_stream.id,
            'propagate_mode': 'change_all',
            'content': 'Not allowed',
        })
        self.assert_json_error(result, "Cannot change message content while changing stream")

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assertEqual(len(messages), 3)

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assertEqual(len(messages), 0)

    def test_move_message_to_stream_and_topic(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_later) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test")

        with queries_captured() as queries:
            result = self.client_patch("/json/messages/" + str(msg_id), {
                'message_id': msg_id,
                'stream_id': new_stream.id,
                'propagate_mode': 'change_all',
                'topic': 'new topic',
            })
        self.assertEqual(len(queries), 50)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].content, f"This topic was moved by @_**Iago|{user_profile.id}** to #**new stream>new topic**")

        messages = get_topic_messages(user_profile, new_stream, "new topic")
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[3].content, f"This topic was moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**")
        self.assert_json_success(result)

    def test_inaccessible_msg_after_stream_change(self) -> None:
        """Simulates the case where message is moved to a stream where user is not a subscribed"""
        (user_profile, old_stream, new_stream, msg_id, msg_id_lt) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test")

        guest_user = self.example_user('polonius')
        non_guest_user = self.example_user('hamlet')
        self.subscribe(guest_user, old_stream.name)
        self.subscribe(non_guest_user, old_stream.name)

        msg_id_to_test_acesss = self.send_stream_message(user_profile, old_stream.name,
                                                         topic_name='test', content="fourth")

        self.assertEqual(has_message_access(guest_user, Message.objects.get(id=msg_id_to_test_acesss), None), True)
        self.assertEqual(has_message_access(non_guest_user, Message.objects.get(id=msg_id_to_test_acesss), None), True)

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'stream_id': new_stream.id,
            'propagate_mode': 'change_all',
            'topic': 'new topic'
        })
        self.assert_json_success(result)

        self.assertEqual(has_message_access(guest_user, Message.objects.get(id=msg_id_to_test_acesss), None), False)
        self.assertEqual(has_message_access(non_guest_user, Message.objects.get(id=msg_id_to_test_acesss), None), True)
        self.assertEqual(UserMessage.objects.filter(
            user_profile_id=non_guest_user.id,
            message_id=msg_id_to_test_acesss,
        ).count(), 0)
        self.assertEqual(has_message_access(self.example_user('iago'), Message.objects.get(id=msg_id_to_test_acesss), None), True)

    def test_no_notify_move_message_to_stream(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_lt) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test")

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'stream_id': new_stream.id,
            'propagate_mode': 'change_all',
            'send_notification_to_old_thread': 'false',
            'send_notification_to_new_thread': 'false',
        })

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assertEqual(len(messages), 0)

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assertEqual(len(messages), 3)

    def test_notify_new_thread_move_message_to_stream(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_lt) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test")

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'stream_id': new_stream.id,
            'propagate_mode': 'change_all',
            'send_notification_to_old_thread': 'false',
            'send_notification_to_new_thread': 'true',
        })

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assertEqual(len(messages), 0)

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[3].content, f"This topic was moved here from #**test move stream>test** by @_**Iago|{user_profile.id}**")

    def test_notify_old_thread_move_message_to_stream(self) -> None:
        (user_profile, old_stream, new_stream, msg_id, msg_id_lt) = self.prepare_move_topics(
            "iago", "test move stream", "new stream", "test")

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'stream_id': new_stream.id,
            'propagate_mode': 'change_all',
            'send_notification_to_old_thread': 'true',
            'send_notification_to_new_thread': 'false',
        })

        self.assert_json_success(result)

        messages = get_topic_messages(user_profile, old_stream, "test")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].content, f"This topic was moved by @_**Iago|{user_profile.id}** to #**new stream>test**")

        messages = get_topic_messages(user_profile, new_stream, "test")
        self.assertEqual(len(messages), 3)

    def parameterized_test_move_message_involving_private_stream(
        self,
        from_invite_only: bool,
        history_public_to_subscribers: bool,
        user_messages_created: bool,
        to_invite_only: bool=True,
    ) -> None:
        admin_user = self.example_user("iago")
        user_losing_access = self.example_user('cordelia')
        user_gaining_access = self.example_user('hamlet')

        self.login("iago")
        old_stream = self.make_stream("test move stream", invite_only=from_invite_only)
        new_stream = self.make_stream("new stream", invite_only=to_invite_only, history_public_to_subscribers=history_public_to_subscribers)

        self.subscribe(admin_user, old_stream.name)
        self.subscribe(user_losing_access, old_stream.name)

        self.subscribe(admin_user, new_stream.name)
        self.subscribe(user_gaining_access, new_stream.name)

        msg_id = self.send_stream_message(admin_user, old_stream.name,
                                          topic_name="test", content="First")
        self.send_stream_message(admin_user, old_stream.name,
                                 topic_name="test", content="Second")

        self.assertEqual(UserMessage.objects.filter(
            user_profile_id=user_losing_access.id,
            message_id=msg_id,
        ).count(), 1)
        self.assertEqual(UserMessage.objects.filter(
            user_profile_id=user_gaining_access.id,
            message_id=msg_id,
        ).count(), 0)

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'stream_id': new_stream.id,
            'propagate_mode': 'change_all',
        })
        self.assert_json_success(result)

        messages = get_topic_messages(admin_user, old_stream, "test")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].content, f"This topic was moved by @_**Iago|{admin_user.id}** to #**new stream>test**")

        messages = get_topic_messages(admin_user, new_stream, "test")
        self.assertEqual(len(messages), 3)

        self.assertEqual(UserMessage.objects.filter(
            user_profile_id=user_losing_access.id,
            message_id=msg_id,
        ).count(), 0)
        # When the history is shared, UserMessage is not created for the user but the user
        # can see the message.
        self.assertEqual(UserMessage.objects.filter(
            user_profile_id=user_gaining_access.id,
            message_id=msg_id,
        ).count(), 1 if user_messages_created else 0)

    def test_move_message_from_public_to_private_stream_not_shared_history(self) -> None:
        self.parameterized_test_move_message_involving_private_stream(
            from_invite_only=False,
            history_public_to_subscribers=False,
            user_messages_created=True,
        )

    def test_move_message_from_public_to_private_stream_shared_history(self) -> None:
        self.parameterized_test_move_message_involving_private_stream(
            from_invite_only=False,
            history_public_to_subscribers=True,
            user_messages_created=False,
        )

    def test_move_message_from_private_to_private_stream_not_shared_history(self) -> None:
        self.parameterized_test_move_message_involving_private_stream(
            from_invite_only=True,
            history_public_to_subscribers=False,
            user_messages_created=True,
        )

    def test_move_message_from_private_to_private_stream_shared_history(self) -> None:
        self.parameterized_test_move_message_involving_private_stream(
            from_invite_only=True,
            history_public_to_subscribers=True,
            user_messages_created=False,
        )

    def test_move_message_from_private_to_public(self) -> None:
        self.parameterized_test_move_message_involving_private_stream(
            from_invite_only=True,
            history_public_to_subscribers=True,
            user_messages_created=False,
            to_invite_only=False,
        )

class DeleteMessageTest(ZulipTestCase):
    def test_delete_message_invalid_request_format(self) -> None:
        self.login('iago')
        hamlet = self.example_user('hamlet')
        msg_id = self.send_stream_message(hamlet, "Scotland")
        result = self.client_delete(f'/json/messages/{msg_id + 1}',
                                    {'message_id': msg_id})
        self.assert_json_error(result, "Invalid message(s)")
        result = self.client_delete(f'/json/messages/{msg_id}')
        self.assert_json_success(result)

    def test_delete_message_by_user(self) -> None:
        def set_message_deleting_params(allow_message_deleting: bool,
                                        message_content_delete_limit_seconds: int) -> None:
            self.login('iago')
            result = self.client_patch("/json/realm", {
                'allow_message_deleting': orjson.dumps(allow_message_deleting).decode(),
                'message_content_delete_limit_seconds': message_content_delete_limit_seconds,
            })
            self.assert_json_success(result)

        def test_delete_message_by_admin(msg_id: int) -> HttpResponse:
            self.login('iago')
            result = self.client_delete(f'/json/messages/{msg_id}')
            return result

        def test_delete_message_by_owner(msg_id: int) -> HttpResponse:
            self.login('hamlet')
            result = self.client_delete(f'/json/messages/{msg_id}')
            return result

        def test_delete_message_by_other_user(msg_id: int) -> HttpResponse:
            self.login('cordelia')
            result = self.client_delete(f'/json/messages/{msg_id}')
            return result

        # Test if message deleting is not allowed(default).
        set_message_deleting_params(False, 0)
        hamlet = self.example_user('hamlet')
        self.login_user(hamlet)
        msg_id = self.send_stream_message(hamlet, "Scotland")

        result = test_delete_message_by_owner(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_other_user(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_admin(msg_id=msg_id)
        self.assert_json_success(result)

        # Test if message deleting is allowed.
        # Test if time limit is zero(no limit).
        set_message_deleting_params(True, 0)
        msg_id = self.send_stream_message(hamlet, "Scotland")
        message = Message.objects.get(id=msg_id)
        message.date_sent = message.date_sent - datetime.timedelta(seconds=600)
        message.save()

        result = test_delete_message_by_other_user(msg_id=msg_id)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_owner(msg_id=msg_id)
        self.assert_json_success(result)

        # Test if time limit is non-zero.
        set_message_deleting_params(True, 240)
        msg_id_1 = self.send_stream_message(hamlet, "Scotland")
        message = Message.objects.get(id=msg_id_1)
        message.date_sent = message.date_sent - datetime.timedelta(seconds=120)
        message.save()

        msg_id_2 = self.send_stream_message(hamlet, "Scotland")
        message = Message.objects.get(id=msg_id_2)
        message.date_sent = message.date_sent - datetime.timedelta(seconds=360)
        message.save()

        result = test_delete_message_by_other_user(msg_id=msg_id_1)
        self.assert_json_error(result, "You don't have permission to delete this message")

        result = test_delete_message_by_owner(msg_id=msg_id_1)
        self.assert_json_success(result)
        result = test_delete_message_by_owner(msg_id=msg_id_2)
        self.assert_json_error(result, "The time limit for deleting this message has passed")

        # No limit for admin.
        result = test_delete_message_by_admin(msg_id=msg_id_2)
        self.assert_json_success(result)

        # Test multiple delete requests with no latency issues
        msg_id = self.send_stream_message(hamlet, "Scotland")
        result = test_delete_message_by_owner(msg_id=msg_id)
        self.assert_json_success(result)
        result = test_delete_message_by_owner(msg_id=msg_id)
        self.assert_json_error(result, "Invalid message(s)")

        # Test handling of 500 error caused by multiple delete requests due to latency.
        # see issue #11219.
        with mock.patch("zerver.views.message_edit.do_delete_messages") as m, \
                mock.patch("zerver.views.message_edit.validate_can_delete_message", return_value=None), \
                mock.patch("zerver.views.message_edit.access_message", return_value=(None, None)):
            m.side_effect = IntegrityError()
            result = test_delete_message_by_owner(msg_id=msg_id)
            self.assert_json_error(result, "Message already deleted")
            m.side_effect = Message.DoesNotExist()
            result = test_delete_message_by_owner(msg_id=msg_id)
            self.assert_json_error(result, "Message already deleted")
