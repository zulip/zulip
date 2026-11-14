import re
from typing import TYPE_CHECKING, Any
from unittest import mock

import orjson
from django.core.exceptions import ValidationError

from zerver.lib.exceptions import MarkdownRenderingError
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.validator import check_widget_content
from zerver.lib.widget import get_widget_data, get_widget_type, render_poll_submessage_content
from zerver.models import SubMessage, UserProfile

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class WidgetContentTestCase(ZulipTestCase):
    def test_validation(self) -> None:
        def assert_error(obj: object, msg: str) -> None:
            with self.assertRaisesRegex(ValidationError, re.escape(msg)):
                check_widget_content(obj)

        assert_error(5, "widget_content is not a dict")

        assert_error({}, "widget_type is not in widget_content")

        assert_error(dict(widget_type="whatever"), "extra_data is not in widget_content")

        assert_error(dict(widget_type="zform", extra_data=4), "extra_data is not a dict")

        assert_error(dict(widget_type="bogus", extra_data={}), "unknown widget type: bogus")

        extra_data: dict[str, Any] = {}
        obj = dict(widget_type="zform", extra_data=extra_data)

        assert_error(obj, "zform is missing type field")

        extra_data["type"] = "bogus"
        assert_error(obj, "unknown zform type: bogus")

        extra_data["type"] = "choices"
        assert_error(obj, "heading key is missing from extra_data")

        extra_data["heading"] = "whatever"
        assert_error(obj, "choices key is missing from extra_data")

        extra_data["choices"] = 99
        assert_error(obj, 'extra_data["choices"] is not a list')

        extra_data["choices"] = [99]
        assert_error(obj, 'extra_data["choices"][0] is not a dict')

        extra_data["choices"] = [
            dict(long_name="foo", reply="bar"),
        ]
        assert_error(obj, 'short_name key is missing from extra_data["choices"][0]')

        extra_data["choices"] = [
            dict(short_name="a", long_name="foo", reply="bar"),
        ]

        check_widget_content(obj)

    def test_message_error_handling(self) -> None:
        sender = self.example_user("cordelia")
        stream_name = "Verona"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content="whatever",
        )

        payload["widget_content"] = "{{{{{{"  # unparsable
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_error_contains(result, "Widgets: API programmer sent invalid JSON")

        bogus_data = dict(color="red", foo="bar", x=2)
        payload["widget_content"] = orjson.dumps(bogus_data).decode()
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_error_contains(result, "Widgets: widget_type is not in widget_content")

    def test_get_widget_data_for_non_widget_messages(self) -> None:
        # This is a pretty important test, despite testing the
        # "negative" case.  We never want widgets to interfere
        # with normal messages.

        test_messages = [
            "",
            "     ",
            "this is an ordinary message",
            "/bogus_command",
            "/me shrugs",
            "use /poll",
        ]

        for message in test_messages:
            self.assertEqual(get_widget_data(content=message), (None, None))

        # Add positive checks for context
        self.assertEqual(
            get_widget_data(content="/todo"), ("todo", {"task_list_title": "", "tasks": []})
        )
        self.assertEqual(
            get_widget_data(content="/todo Title"),
            ("todo", {"task_list_title": "Title", "tasks": []}),
        )
        # Test tokenization on newline character
        self.assertEqual(
            get_widget_data(content="/todo\nTask"),
            ("todo", {"task_list_title": "", "tasks": [{"task": "Task", "desc": ""}]}),
        )

    def test_explicit_widget_content(self) -> None:
        # Users can send widget_content directly on messages
        # using the `widget_content` field.

        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "does-not-matter"
        zform_data = dict(
            type="choices",
            heading="Options:",
            choices=[],
        )

        widget_content = dict(
            widget_type="zform",
            extra_data=zform_data,
        )

        check_widget_content(widget_content)

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
            widget_content=orjson.dumps(widget_content).decode(),
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="zform",
            extra_data=zform_data,
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

    def test_todo(self) -> None:
        # This also helps us get test coverage that could apply
        # to future widgets.

        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "/todo"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="todo",
            extra_data={"task_list_title": "", "tasks": []},
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

        content = "/todo Example Task List Title"
        payload["content"] = content
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="todo",
            extra_data={"task_list_title": "Example Task List Title", "tasks": []},
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

        # We test for both trailing and leading spaces, along with blank lines
        # for the tasks.
        content = "/todo Example Task List Title\n\n    task without description\ntask: with description    \n\n - task as list : also with description"
        payload["content"] = content
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="todo",
            extra_data=dict(
                task_list_title="Example Task List Title",
                tasks=[
                    dict(
                        task="task without description",
                        desc="",
                    ),
                    dict(
                        task="task",
                        desc="with description",
                    ),
                    dict(
                        task="task as list",
                        desc="also with description",
                    ),
                ],
            ),
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

    def test_poll_command_extra_data(self) -> None:
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        # We test for both trailing and leading spaces, along with blank lines
        # for the poll options.
        content = "/poll What is your favorite color?\n\nRed\nGreen  \n\n   Blue\n - Yellow"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="poll",
            extra_data=dict(
                options=["Red", "Green", "Blue", "Yellow"],
                question="What is your favorite color?",
                rendered_options_html=["Red", "Green", "Blue", "Yellow"],
                rendered_question_html="What is your favorite color?",
            ),
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

        # Now don't supply a question.

        content = "/poll"
        payload["content"] = content
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        expected_submessage_content = dict(
            widget_type="poll",
            extra_data=dict(
                options=[],
                question="",
                rendered_options_html=[],
                rendered_question_html="",
            ),
        )

        message = self.get_last_message()
        self.assertEqual(message.content, content)
        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

    def test_todo_command_extra_data(self) -> None:
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        # We test for leading spaces.
        content = "/todo   School Work"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="todo",
            extra_data=dict(task_list_title="School Work", tasks=[]),
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

        # Now don't supply a task list title.

        content = "/todo"
        payload["content"] = content
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        expected_submessage_content = dict(
            widget_type="todo",
            extra_data=dict(task_list_title="", tasks=[]),
        )

        message = self.get_last_message()
        self.assertEqual(message.content, content)
        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)
        # Now supply both task list title and tasks.

        content = "/todo School Work\nchemistry homework: assignment 2\nstudy for english test: pages 56-67"
        payload["content"] = content
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        expected_submessage_content = dict(
            widget_type="todo",
            extra_data=dict(
                task_list_title="School Work",
                tasks=[
                    dict(
                        task="chemistry homework",
                        desc="assignment 2",
                    ),
                    dict(
                        task="study for english test",
                        desc="pages 56-67",
                    ),
                ],
            ),
        )

        message = self.get_last_message()
        self.assertEqual(message.content, content)
        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, "widget")
        self.assertEqual(orjson.loads(submessage.content), expected_submessage_content)

    def test_poll_permissions(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        stream_name = "Verona"
        content = "/poll Preference?\n\nyes\nno"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(cordelia, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()

        def post(sender: UserProfile, data: dict[str, object]) -> "TestHttpResponse":
            payload = dict(
                message_id=message.id, msg_type="widget", content=orjson.dumps(data).decode()
            )
            return self.api_post(sender, "/api/v1/submessage", payload)

        result = post(cordelia, dict(type="question", question="Tabs or spaces?"))
        self.assert_json_success(result)

        result = post(hamlet, dict(type="question", question="Tabs or spaces?"))
        self.assert_json_error(result, "You can't edit a question unless you are the author.")

    def test_todo_permissions(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        stream_name = "Verona"
        content = "/todo School Work"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(cordelia, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()

        def post(sender: UserProfile, data: dict[str, object]) -> "TestHttpResponse":
            payload = dict(
                message_id=message.id, msg_type="widget", content=orjson.dumps(data).decode()
            )
            return self.api_post(sender, "/api/v1/submessage", payload)

        result = post(cordelia, dict(type="new_task_list_title", title="School Work"))
        self.assert_json_success(result)

        result = post(hamlet, dict(type="new_task_list_title", title="School Work"))
        self.assert_json_error(
            result, "You can't edit the task list title unless you are the author."
        )

    def test_poll_type_validation(self) -> None:
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "/poll Preference?\n\nyes\nno"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()

        def post_submessage(content: str) -> "TestHttpResponse":
            payload = dict(
                message_id=message.id,
                msg_type="widget",
                content=content,
            )
            return self.api_post(sender, "/api/v1/submessage", payload)

        def assert_error(content: str, error: str) -> None:
            result = post_submessage(content)
            self.assert_json_error_contains(result, error)

        assert_error("bogus", "Invalid json for submessage")
        assert_error('""', "not a dict")
        assert_error("[]", "not a dict")

        assert_error('{"type": "bogus"}', "Unknown type for poll data: bogus")
        assert_error('{"type": "vote"}', "key is missing")
        assert_error('{"type": "vote", "key": "1,1,", "vote": 99}', "Invalid poll data")

        assert_error('{"type": "question"}', "key is missing")
        assert_error('{"type": "question", "question": 7}', "not a string")

        assert_error('{"type": "new_option"}', "key is missing")
        assert_error('{"type": "new_option", "idx": 7, "option": 999}', "not a string")
        assert_error('{"type": "new_option", "idx": -1, "option": "pizza"}', "too small")
        assert_error('{"type": "new_option", "idx": 1001, "option": "pizza"}', "too large")
        assert_error('{"type": "new_option", "idx": "bogus", "option": "maybe"}', "not an int")

        def assert_success(data: dict[str, object]) -> None:
            content = orjson.dumps(data).decode()
            result = post_submessage(content)
            self.assert_json_success(result)

        # Note that we only validate for types. The server code may, for,
        # example, allow a vote for a non-existing option, and we rely
        # on the clients to ignore those.

        assert_success(dict(type="vote", key="1,1", vote=1))
        assert_success(dict(type="new_option", idx=7, option="maybe"))
        assert_success(dict(type="question", question="what's for dinner?"))

    def test_todo_type_validation(self) -> None:
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "/todo"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()

        def post_submessage(content: str) -> "TestHttpResponse":
            payload = dict(
                message_id=message.id,
                msg_type="widget",
                content=content,
            )
            return self.api_post(sender, "/api/v1/submessage", payload)

        def assert_error(content: str, error: str) -> None:
            result = post_submessage(content)
            self.assert_json_error_contains(result, error)

        assert_error('{"type": "bogus"}', "Unknown type for todo data: bogus")

        assert_error('{"type": "new_task"}', "key is missing")
        assert_error(
            '{"type": "new_task", "key": 7, "task": 7, "desc": "", "completed": false}',
            'data["task"] is not a string',
        )
        assert_error(
            '{"type": "new_task", "key": -1, "task": "eat", "desc": "", "completed": false}',
            'data["key"] is too small',
        )
        assert_error(
            '{"type": "new_task", "key": 1001, "task": "eat", "desc": "", "completed": false}',
            'data["key"] is too large',
        )

        assert_error('{"type": "strike"}', "key is missing")
        assert_error('{"type": "strike", "key": 999}', 'data["key"] is not a string')

        def assert_success(data: dict[str, object]) -> None:
            content = orjson.dumps(data).decode()
            result = post_submessage(content)
            self.assert_json_success(result)

        assert_success(dict(type="new_task", key=7, task="eat", desc="", completed=False))
        assert_success(dict(type="strike", key="5,9"))

    def test_poll_option_inline_markdown(self) -> None:
        """Test that poll options are rendered with inline markdown."""
        sender = self.example_user("cordelia")
        stream_name = "Verona"

        # Test emoji, links, timestamps, and formatting in poll options.
        content = (
            "/poll When should we meet?\n"
            "- 10am :tada:\n"
            "- [Zoom link](https://zoom.us/j/123)\n"
            "- **Bold option**\n"
            "- <time:2024-01-15T10:00:00Z>"
        )

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        submessage = SubMessage.objects.get(message_id=message.id)
        submessage_data = orjson.loads(submessage.content)

        extra_data = submessage_data["extra_data"]

        # Raw text is preserved.
        self.assertEqual(extra_data["question"], "When should we meet?")
        self.assertEqual(
            extra_data["options"],
            [
                "10am :tada:",
                "[Zoom link](https://zoom.us/j/123)",
                "**Bold option**",
                "<time:2024-01-15T10:00:00Z>",
            ],
        )

        # Rendered fields are present.
        self.assertIn("rendered_question_html", extra_data)
        self.assertIn("rendered_options_html", extra_data)
        self.assert_length(extra_data["rendered_options_html"], 4)

        # Emoji is rendered.
        self.assertIn("emoji", extra_data["rendered_options_html"][0])

        # Link is rendered.
        self.assertIn('<a href="https://zoom.us/j/123"', extra_data["rendered_options_html"][1])

        # Bold is rendered.
        self.assertIn("<strong>", extra_data["rendered_options_html"][2])

        # Timestamp is rendered.
        self.assertIn("<time", extra_data["rendered_options_html"][3])

    def test_poll_submessage_new_option_rendered(self) -> None:
        """Test that new_option submessages include rendered content."""
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "/poll Preference?\n\nyes\nno"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)
        message = self.get_last_message()

        # Add an option with emoji.
        option_data = dict(type="new_option", idx=1, option="party :tada:")
        submessage_payload: dict[str, object] = dict(
            message_id=message.id,
            msg_type="widget",
            content=orjson.dumps(option_data).decode(),
        )
        result = self.api_post(sender, "/api/v1/submessage", submessage_payload)
        self.assert_json_success(result)

        # The latest submessage should have rendered_option_html.
        submessages = SubMessage.objects.filter(message_id=message.id).order_by("id")
        new_option_submessage = submessages.last()
        assert new_option_submessage is not None
        data = orjson.loads(new_option_submessage.content)
        self.assertEqual(data["option"], "party :tada:")
        self.assertIn("rendered_option_html", data)
        self.assertIn("emoji", data["rendered_option_html"])

    def test_poll_submessage_question_rendered(self) -> None:
        """Test that question update submessages include rendered content."""
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "/poll Preference?\n\nyes\nno"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)
        message = self.get_last_message()

        # Update the question with a link.
        question_data = dict(type="question", question="See [details](https://example.com)")
        submessage_payload: dict[str, object] = dict(
            message_id=message.id,
            msg_type="widget",
            content=orjson.dumps(question_data).decode(),
        )
        result = self.api_post(sender, "/api/v1/submessage", submessage_payload)
        self.assert_json_success(result)

        submessages = SubMessage.objects.filter(message_id=message.id).order_by("id")
        question_submessage = submessages.last()
        assert question_submessage is not None
        data = orjson.loads(question_submessage.content)
        self.assertEqual(data["question"], "See [details](https://example.com)")
        self.assertIn("rendered_question_html", data)
        self.assertIn('<a href="https://example.com"', data["rendered_question_html"])

    def test_poll_options_without_rendered_fields_fallback(self) -> None:
        """Test that polls without rendered fields (old data) still work."""
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "/poll Preference?\n\nyes\nno"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)
        message = self.get_last_message()

        # Simulate old-format submessage without rendered fields by
        # directly modifying the stored content.
        submessage = SubMessage.objects.get(message_id=message.id)
        old_format_content = orjson.dumps(
            {
                "widget_type": "poll",
                "extra_data": {
                    "question": "Preference?",
                    "options": ["yes", "no"],
                },
            }
        ).decode()
        submessage.content = old_format_content
        submessage.save()

        # Verify the old-format data is preserved and accessible.
        submessage.refresh_from_db()
        data = orjson.loads(submessage.content)
        self.assertEqual(data["extra_data"]["question"], "Preference?")
        self.assertEqual(data["extra_data"]["options"], ["yes", "no"])
        self.assertNotIn("rendered_question_html", data["extra_data"])
        self.assertNotIn("rendered_options_html", data["extra_data"])

    def test_poll_rendering_failure_degrades_gracefully(self) -> None:
        """Test that MarkdownRenderingError in render_poll_extra_data
        produces empty rendered fields instead of breaking poll creation."""
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "/poll Favorite color?\nRed\nBlue"

        with mock.patch(
            "zerver.lib.markdown.markdown_convert_inline",
            side_effect=MarkdownRenderingError,
        ):
            payload = dict(
                type="stream",
                to=orjson.dumps(stream_name).decode(),
                topic="whatever",
                content=content,
            )
            result = self.api_post(sender, "/api/v1/messages", payload)
            self.assert_json_success(result)

        message = self.get_last_message()
        submessage = SubMessage.objects.get(message_id=message.id)
        submessage_data = orjson.loads(submessage.content)
        extra_data = submessage_data["extra_data"]

        # Raw text is preserved.
        self.assertEqual(extra_data["question"], "Favorite color?")
        self.assertEqual(extra_data["options"], ["Red", "Blue"])

        # Rendered fields fall back to empty strings.
        self.assertEqual(extra_data["rendered_question_html"], "")
        self.assertEqual(extra_data["rendered_options_html"], ["", ""])

    def test_poll_submessage_rendering_failure_degrades_gracefully(self) -> None:
        """Test that MarkdownRenderingError in render_poll_submessage_content
        returns unmodified content instead of a 500."""
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        content = "/poll Preference?\n\nyes\nno"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)
        message = self.get_last_message()

        option_data = dict(type="new_option", idx=1, option="maybe")
        submessage_payload: dict[str, object] = dict(
            message_id=message.id,
            msg_type="widget",
            content=orjson.dumps(option_data).decode(),
        )

        with mock.patch(
            "zerver.lib.markdown.markdown_convert_inline",
            side_effect=MarkdownRenderingError,
        ):
            result = self.api_post(sender, "/api/v1/submessage", submessage_payload)
            self.assert_json_success(result)

        # The submessage was saved successfully.
        submessages = SubMessage.objects.filter(message_id=message.id).order_by("id")
        new_option_submessage = submessages.last()
        assert new_option_submessage is not None
        data = orjson.loads(new_option_submessage.content)

        # Raw text is preserved, but no rendered field because rendering failed.
        self.assertEqual(data["option"], "maybe")
        self.assertNotIn("rendered_option_html", data)

    def test_get_widget_type(self) -> None:
        sender = self.example_user("cordelia")
        stream_name = "Verona"
        # We test for both trailing and leading spaces, along with blank lines
        # for the poll options.
        content = "/poll Preference?\n\nyes\nno"

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content,
        )
        result = self.api_post(sender, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()

        [submessage] = SubMessage.objects.filter(message_id=message.id)

        self.assertEqual(get_widget_type(message_id=message.id), "poll")

        submessage.content = "bogus non-json"
        submessage.save()
        self.assertEqual(get_widget_type(message_id=message.id), None)

        submessage.content = '{"bogus": 1}'
        submessage.save()
        self.assertEqual(get_widget_type(message_id=message.id), None)

        submessage.content = '{"widget_type": "todo"}'
        submessage.save()
        self.assertEqual(get_widget_type(message_id=message.id), "todo")

    def test_render_poll_submessage_content_invalid_json(self) -> None:
        invalid = "not-valid-json{{{"
        self.assertEqual(render_poll_submessage_content(invalid, None), invalid)

    def test_render_poll_submessage_content_non_dict_json(self) -> None:
        array_content = "[1, 2, 3]"
        self.assertEqual(render_poll_submessage_content(array_content, None), array_content)
