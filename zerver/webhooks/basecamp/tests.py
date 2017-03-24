# -*- coding: utf-8 -*-
from typing import Text
from zerver.lib.test_classes import WebhookTestCase

class BasecampHookTests(WebhookTestCase):
    STREAM_NAME = 'basecamp'
    URL_TEMPLATE = u"/api/v1/external/basecamp?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'basecamp'
    EXPECTED_SUBJECT = "Zulip HQ"

    def test_basecamp_makes_doc_active(self):
        # type: () -> None
        expected_message = u"Tomasz activated the document [New doc](https://3.basecamp.com/3688623/buckets/2957043/documents/432522214)"
        self._send_and_test_message('doc_active', expected_message)

    def test_basecamp_makes_doc_archived(self):
        # type: () -> None
        expected_message = u"Tomasz archived the document [new doc](https://3.basecamp.com/3688623/buckets/2957043/documents/434455988)"
        self._send_and_test_message('doc_archived', expected_message)

    def test_basecamp_makes_doc_changed_content(self):
        # type: () -> None
        expected_message = u"Tomasz changed content of the document [New doc edit](https://3.basecamp.com/3688623/buckets/2957043/documents/432522214)"
        self._send_and_test_message('doc_content_changed', expected_message)

    def test_basecamp_makes_doc_changed_title(self):
        # type: () -> None
        expected_message = u"Tomasz changed title of the document [New doc edit](https://3.basecamp.com/3688623/buckets/2957043/documents/432522214)"
        self._send_and_test_message('doc_title_changed', expected_message)

    def test_basecamp_makes_doc_publicized(self):
        # type: () -> None
        expected_message = u"Tomasz publicized the document [new doc](https://3.basecamp.com/3688623/buckets/2957043/documents/434455988)"
        self._send_and_test_message('doc_publicized', expected_message)

    def test_basecamp_makes_doc_created(self):
        # type: () -> None
        expected_message = u"Tomasz created the document [new doc](https://3.basecamp.com/3688623/buckets/2957043/documents/434455988)"
        self._send_and_test_message('doc_created', expected_message)

    def test_basecamp_makes_doc_trashed(self):
        # type: () -> None
        expected_message = u"Tomasz trashed the document [new doc](https://3.basecamp.com/3688623/buckets/2957043/documents/434455988)"
        self._send_and_test_message('doc_trashed', expected_message)

    def test_basecamp_makes_doc_unarchived(self):
        # type: () -> None
        expected_message = u"Tomasz unarchived the document [new doc](https://3.basecamp.com/3688623/buckets/2957043/documents/434455988)"
        self._send_and_test_message('doc_unarchive', expected_message)

    def test_basecamp_makes_questions_answer_archived(self):
        # type: () -> None
        expected_message = u"Tomasz archived the [answer](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747/answers/2017-03-16#__recording_432529636) of the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)"
        self._send_and_test_message('questions_answer_archived', expected_message)

    def test_basecamp_makes_questions_answer_content_changed(self):
        # type: () -> None
        expected_message = u"Tomasz changed content of the [answer](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747/answers/2017-03-16#__recording_432529636) of the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)"
        self._send_and_test_message('questions_answer_content_changed', expected_message)

    def test_basecamp_makes_questions_answer_created(self):
        # type: () -> None
        expected_message = u"Tomasz created the [answer](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747/answers/2017-03-16#__recording_432529636) of the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)"
        self._send_and_test_message('questions_answer_created', expected_message)

    def test_basecamp_makes_questions_answer_trashed(self):
        # type: () -> None
        expected_message = u"Tomasz trashed the [answer](https://3.basecamp.com/3688623/buckets/2957043/question_answers/432529636) of the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)"
        self._send_and_test_message('questions_answer_trashed', expected_message)

    def test_basecamp_makes_questions_answer_unarchived(self):
        # type: () -> None
        expected_message = u"Tomasz unarchived the [answer](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747/answers/2017-03-16#__recording_432529636) of the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)"
        self._send_and_test_message('questions_answer_unarchived', expected_message)

    def test_basecamp_makes_question_archived(self):
        # type: () -> None
        expected_message = u"Tomasz archived the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)"
        self._send_and_test_message('question_archived', expected_message)

    def test_basecamp_makes_question_created(self):
        # type: () -> None
        expected_message = u"Tomasz created the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)"
        self._send_and_test_message('question_created', expected_message)

    def test_basecamp_makes_question_trashed(self):
        # type: () -> None
        expected_message = u"Tomasz trashed the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)"
        self._send_and_test_message('question_trashed', expected_message)

    def test_basecamp_makes_question_unarchived(self):
        # type: () -> None
        expected_message = u"Tomasz unarchived the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)"
        self._send_and_test_message('question_unarchived', expected_message)

    def test_basecamp_makes_message_archived(self):
        # type: () -> None
        expected_message = u"Tomasz archived the message [Message Title new](https://3.basecamp.com/3688623/buckets/2957043/messages/430680605)"
        self._send_and_test_message('message_archived', expected_message)

    def test_basecamp_makes_message_content_change(self):
        # type: () -> None
        expected_message = u"Tomasz changed content of the message [Message Title new](https://3.basecamp.com/3688623/buckets/2957043/messages/430680605)"
        self._send_and_test_message('message_content_changed', expected_message)

    def test_basecamp_makes_message_created(self):
        # type: () -> None
        expected_message = u"Tomasz created the message [Message Title](https://3.basecamp.com/3688623/buckets/2957043/messages/430680605)"
        self._send_and_test_message('message_created', expected_message)

    def test_basecamp_makes_message_title_change(self):
        # type: () -> None
        expected_message = u"Tomasz changed subject of the message [Message Title new](https://3.basecamp.com/3688623/buckets/2957043/messages/430680605)"
        self._send_and_test_message('message_title_changed', expected_message)

    def test_basecamp_makes_message_trashed(self):
        # type: () -> None
        expected_message = u"Tomasz trashed the message [Message Title new](https://3.basecamp.com/3688623/buckets/2957043/messages/430680605)"
        self._send_and_test_message('message_trashed', expected_message)

    def test_basecamp_makes_message_unarchived(self):
        # type: () -> None
        expected_message = u"Tomasz unarchived the message [Message Title new](https://3.basecamp.com/3688623/buckets/2957043/messages/430680605)"
        self._send_and_test_message('message_unarchived', expected_message)

    def test_basecamp_makes_todo_list_created(self):
        # type: () -> None
        expected_message = u"Tomasz created the todo list [NEW TO DO LIST](https://3.basecamp.com/3688623/buckets/2957043/todolists/427050190)"
        self._send_and_test_message('todo_list_created', expected_message)

    def test_basecamp_makes_todo_list_description_changed(self):
        # type: () -> None
        expected_message = u"Tomasz changed description of the todo list [NEW TO DO LIST](https://3.basecamp.com/3688623/buckets/2957043/todolists/427050190)"
        self._send_and_test_message('todo_list_description_changed', expected_message)

    def test_basecamp_makes_todo_list_modified(self):
        # type: () -> None
        expected_message = u"Tomasz changed name of the todo list [NEW Name TO DO LIST](https://3.basecamp.com/3688623/buckets/2957043/todolists/427050190)"
        self._send_and_test_message('todo_list_name_changed', expected_message)

    def test_basecamp_makes_todo_assignment_changed(self):
        # type: () -> None
        expected_message = u"Tomasz changed assignment of the todo task [New task](https://3.basecamp.com/3688623/buckets/2957043/todos/427055624)"
        self._send_and_test_message('todo_assignment_changed', expected_message)

    def test_basecamp_makes_todo_completed(self):
        # type: () -> None
        expected_message = u"Tomasz completed the todo task [New task](https://3.basecamp.com/3688623/buckets/2957043/todos/427055624)"
        self._send_and_test_message('todo_completed', expected_message)

    def test_basecamp_makes_todo_created(self):
        # type: () -> None
        expected_message = u"Tomasz created the todo task [New task](https://3.basecamp.com/3688623/buckets/2957043/todos/427055624)"
        self._send_and_test_message('todo_created', expected_message)

    def test_basecamp_makes_comment_created(self):
        # type: () -> None
        expected_message = u"Tomasz created the [comment](https://3.basecamp.com/3688623/buckets/2957043/todos/427055624#__recording_427058780) of the task [New task](https://3.basecamp.com/3688623/buckets/2957043/todos/427055624)"
        self._send_and_test_message('comment_created', expected_message)

    def _send_and_test_message(self, fixture_name, expected_message):
        # type: (Text, Text) -> None
        self.send_and_test_stream_message(fixture_name, self.EXPECTED_SUBJECT, expected_message)
