from zerver.lib.test_classes import WebhookTestCase

TOPIC_NAME = "Zulip HQ"


class BasecampHookTests(WebhookTestCase):
    CHANNEL_NAME = "basecamp"
    URL_TEMPLATE = "/api/v1/external/basecamp?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "basecamp"

    def test_basecamp_makes_doc_active(self) -> None:
        expected_message = "Tomasz activated the document [New doc](https://3.basecamp.com/3688623/buckets/2957043/documents/432522214)."
        self._send_and_test_message("doc_active", expected_message)

    def test_basecamp_makes_doc_archived(self) -> None:
        expected_message = "Tomasz archived the document [new doc](https://3.basecamp.com/3688623/buckets/2957043/documents/434455988)."
        self._send_and_test_message("doc_archived", expected_message)

    def test_basecamp_makes_doc_changed_content(self) -> None:
        expected_message = "Tomasz changed content of the document [New doc edit](https://3.basecamp.com/3688623/buckets/2957043/documents/432522214)."
        self._send_and_test_message("doc_content_changed", expected_message)

    def test_basecamp_makes_doc_changed_title(self) -> None:
        expected_message = "Tomasz changed title of the document [New doc edit](https://3.basecamp.com/3688623/buckets/2957043/documents/432522214)."
        self._send_and_test_message("doc_title_changed", expected_message)

    def test_basecamp_makes_doc_publicized(self) -> None:
        expected_message = "Tomasz publicized the document [new doc](https://3.basecamp.com/3688623/buckets/2957043/documents/434455988)."
        self._send_and_test_message("doc_publicized", expected_message)

    def test_basecamp_makes_doc_created(self) -> None:
        expected_message = "Tomasz created the document [new doc](https://3.basecamp.com/3688623/buckets/2957043/documents/434455988)."
        self._send_and_test_message("doc_created", expected_message)

    def test_basecamp_makes_doc_trashed(self) -> None:
        expected_message = "Tomasz trashed the document [new doc](https://3.basecamp.com/3688623/buckets/2957043/documents/434455988)."
        self._send_and_test_message("doc_trashed", expected_message)

    def test_basecamp_makes_doc_unarchived(self) -> None:
        expected_message = "Tomasz unarchived the document [new doc](https://3.basecamp.com/3688623/buckets/2957043/documents/434455988)."
        self._send_and_test_message("doc_unarchive", expected_message)

    def test_basecamp_makes_questions_answer_archived(self) -> None:
        expected_message = "Tomasz archived the [answer](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747/answers/2017-03-16#__recording_432529636) of the question [Question?](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)"
        self._send_and_test_message("questions_answer_archived", expected_message)

    def test_basecamp_makes_questions_answer_content_changed(self) -> None:
        expected_message = "Tomasz changed content of the [answer](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747/answers/2017-03-16#__recording_432529636) of the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)."
        self._send_and_test_message("questions_answer_content_changed", expected_message)

    def test_basecamp_makes_questions_answer_created(self) -> None:
        expected_message = "Tomasz created the [answer](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747/answers/2017-03-16#__recording_432529636) of the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)."
        self._send_and_test_message("questions_answer_created", expected_message)

    def test_basecamp_makes_questions_answer_trashed(self) -> None:
        expected_message = "Tomasz trashed the [answer](https://3.basecamp.com/3688623/buckets/2957043/question_answers/432529636) of the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)."
        self._send_and_test_message("questions_answer_trashed", expected_message)

    def test_basecamp_makes_questions_answer_unarchived(self) -> None:
        expected_message = "Tomasz unarchived the [answer](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747/answers/2017-03-16#__recording_432529636) of the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)."
        self._send_and_test_message("questions_answer_unarchived", expected_message)

    def test_basecamp_makes_question_archived(self) -> None:
        expected_message = "Tomasz archived the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)."
        self._send_and_test_message("question_archived", expected_message)

    def test_basecamp_makes_question_created(self) -> None:
        expected_message = "Tomasz created the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)."
        self._send_and_test_message("question_created", expected_message)

    def test_basecamp_makes_question_trashed(self) -> None:
        expected_message = "Tomasz trashed the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)."
        self._send_and_test_message("question_trashed", expected_message)

    def test_basecamp_makes_question_unarchived(self) -> None:
        expected_message = "Tomasz unarchived the question [Question](https://3.basecamp.com/3688623/buckets/2957043/questions/432527747)."
        self._send_and_test_message("question_unarchived", expected_message)

    def test_basecamp_makes_message_archived(self) -> None:
        expected_message = "Tomasz archived the message [Message Title new](https://3.basecamp.com/3688623/buckets/2957043/messages/430680605)."
        self._send_and_test_message("message_archived", expected_message)

    def test_basecamp_makes_message_content_change(self) -> None:
        expected_message = "Tomasz changed content of the message [Message Title new](https://3.basecamp.com/3688623/buckets/2957043/messages/430680605)."
        self._send_and_test_message("message_content_changed", expected_message)

    def test_basecamp_makes_message_created(self) -> None:
        expected_message = "Tomasz created the message [Message Title](https://3.basecamp.com/3688623/buckets/2957043/messages/430680605)."
        self._send_and_test_message("message_created", expected_message)

    def test_basecamp_makes_message_title_change(self) -> None:
        expected_message = "Tomasz changed subject of the message [Message Title new](https://3.basecamp.com/3688623/buckets/2957043/messages/430680605)."
        self._send_and_test_message("message_title_changed", expected_message)

    def test_basecamp_makes_message_trashed(self) -> None:
        expected_message = "Tomasz trashed the message [Message Title new](https://3.basecamp.com/3688623/buckets/2957043/messages/430680605)."
        self._send_and_test_message("message_trashed", expected_message)

    def test_basecamp_makes_message_unarchived(self) -> None:
        expected_message = "Tomasz unarchived the message [Message Title new](https://3.basecamp.com/3688623/buckets/2957043/messages/430680605)."
        self._send_and_test_message("message_unarchived", expected_message)

    def test_basecamp_makes_todo_list_created(self) -> None:
        expected_message = "Tomasz created the todo list [NEW TO DO LIST](https://3.basecamp.com/3688623/buckets/2957043/todolists/427050190)."
        self._send_and_test_message("todo_list_created", expected_message)

    def test_basecamp_makes_todo_list_description_changed(self) -> None:
        expected_message = "Tomasz changed description of the todo list [NEW TO DO LIST](https://3.basecamp.com/3688623/buckets/2957043/todolists/427050190)."
        self._send_and_test_message("todo_list_description_changed", expected_message)

    def test_basecamp_makes_todo_list_modified(self) -> None:
        expected_message = "Tomasz changed name of the todo list [NEW Name TO DO LIST](https://3.basecamp.com/3688623/buckets/2957043/todolists/427050190)."
        self._send_and_test_message("todo_list_name_changed", expected_message)

    def test_basecamp_makes_todo_assignment_changed(self) -> None:
        expected_message = "Tomasz changed assignment of the todo task [New task](https://3.basecamp.com/3688623/buckets/2957043/todos/427055624)."
        self._send_and_test_message("todo_assignment_changed", expected_message)

    def test_basecamp_makes_todo_completed(self) -> None:
        expected_message = "Tomasz completed the todo task [New task](https://3.basecamp.com/3688623/buckets/2957043/todos/427055624)."
        self._send_and_test_message("todo_completed", expected_message)

    def test_basecamp_makes_todo_uncompleted(self) -> None:
        expected_message = "Tomasz uncompleted the todo task [New task](https://3.basecamp.com/3688623/buckets/2957043/todos/427055624)."
        self._send_and_test_message("todo_uncompleted", expected_message)

    def test_basecamp_makes_todo_created(self) -> None:
        expected_message = "Tomasz created the todo task [New task](https://3.basecamp.com/3688623/buckets/2957043/todos/427055624)."
        self._send_and_test_message("todo_created", expected_message)

    def test_basecamp_makes_todo_due_on_changed(self) -> None:
        expected_message = "Tomasz changed due_on of the todo task [New task](https://3.basecamp.com/3688623/buckets/2957043/todos/427055624)."
        self._send_and_test_message("todo_due_on_changed", expected_message)

    def test_basecamp_makes_comment_created(self) -> None:
        expected_message = "Tomasz created the [comment](https://3.basecamp.com/3688623/buckets/2957043/todos/427055624#__recording_427058780) of the task [New task](https://3.basecamp.com/3688623/buckets/2957043/todos/427055624)."
        self._send_and_test_message("comment_created", expected_message)

    def _send_and_test_message(self, fixture_name: str, expected_message: str) -> None:
        self.check_webhook(fixture_name, TOPIC_NAME, expected_message)
