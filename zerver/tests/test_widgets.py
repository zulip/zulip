import re
from typing import TYPE_CHECKING, Any

import orjson
from django.core.exceptions import ValidationError

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.validator import check_widget_content
from zerver.lib.widget import get_widget_data, get_widget_type
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


class FreeformWidgetValidationTestCase(ZulipTestCase):
    """Tests for freeform widget validation, including dependencies."""

    def test_freeform_widget_basic_validation(self) -> None:
        """Test basic freeform widget structure."""
        # Valid minimal freeform widget
        widget = {
            "widget_type": "freeform",
            "extra_data": {"html": "<div>Hello</div>"},
        }
        check_widget_content(widget)

        # With optional fields
        widget_with_css_js = {
            "widget_type": "freeform",
            "extra_data": {
                "html": "<div id='app'></div>",
                "css": ".app { color: red; }",
                "js": "console.log('hello');",
            },
        }
        check_widget_content(widget_with_css_js)

    def test_freeform_widget_missing_html(self) -> None:
        """Test that html field is required for freeform widgets."""
        widget = {
            "widget_type": "freeform",
            "extra_data": {"css": "body { }"},
        }
        with self.assertRaisesRegex(ValidationError, "html key is missing"):
            check_widget_content(widget)

    def test_freeform_widget_dependencies_valid(self) -> None:
        """Test valid dependencies in freeform widgets."""
        widget = {
            "widget_type": "freeform",
            "extra_data": {
                "html": "<div>App</div>",
                "dependencies": [
                    {"url": "https://cdn.example.com/lib.js", "type": "script"},
                    {"url": "https://cdn.example.com/style.css", "type": "style"},
                ],
            },
        }
        check_widget_content(widget)

    def test_freeform_widget_dependencies_empty_list(self) -> None:
        """Test that empty dependencies list is valid."""
        widget = {
            "widget_type": "freeform",
            "extra_data": {
                "html": "<div>App</div>",
                "dependencies": [],
            },
        }
        check_widget_content(widget)

    def test_freeform_widget_dependencies_invalid_type(self) -> None:
        """Test that dependency type must be 'script' or 'style'."""
        widget = {
            "widget_type": "freeform",
            "extra_data": {
                "html": "<div>App</div>",
                "dependencies": [
                    {"url": "https://example.com/lib.js", "type": "invalid"},
                ],
            },
        }
        with self.assertRaisesRegex(ValidationError, "Invalid"):
            check_widget_content(widget)

    def test_freeform_widget_dependencies_missing_url(self) -> None:
        """Test that url field is required in dependencies."""
        widget = {
            "widget_type": "freeform",
            "extra_data": {
                "html": "<div>App</div>",
                "dependencies": [
                    {"type": "script"},
                ],
            },
        }
        with self.assertRaisesRegex(ValidationError, "url key is missing"):
            check_widget_content(widget)

    def test_freeform_widget_dependencies_missing_type(self) -> None:
        """Test that type field is required in dependencies."""
        widget = {
            "widget_type": "freeform",
            "extra_data": {
                "html": "<div>App</div>",
                "dependencies": [
                    {"url": "https://example.com/lib.js"},
                ],
            },
        }
        with self.assertRaisesRegex(ValidationError, "type key is missing"):
            check_widget_content(widget)

    def test_freeform_widget_dependencies_not_list(self) -> None:
        """Test that dependencies must be a list."""
        widget = {
            "widget_type": "freeform",
            "extra_data": {
                "html": "<div>App</div>",
                "dependencies": {"url": "https://example.com/lib.js", "type": "script"},
            },
        }
        with self.assertRaisesRegex(ValidationError, "is not a list"):
            check_widget_content(widget)

    def test_freeform_widget_dependencies_url_not_string(self) -> None:
        """Test that dependency URL must be a string."""
        widget = {
            "widget_type": "freeform",
            "extra_data": {
                "html": "<div>App</div>",
                "dependencies": [
                    {"url": 12345, "type": "script"},
                ],
            },
        }
        with self.assertRaisesRegex(ValidationError, "is not a string"):
            check_widget_content(widget)


class InteractiveWidgetValidationTestCase(ZulipTestCase):
    """Tests for interactive widget validation (buttons, select menus)."""

    def test_interactive_widget_button(self) -> None:
        """Test valid button component."""
        widget = {
            "widget_type": "interactive",
            "extra_data": {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {"type": "button", "label": "Click me", "custom_id": "btn1"},
                        ],
                    }
                ]
            },
        }
        check_widget_content(widget)

    def test_interactive_widget_button_with_all_options(self) -> None:
        """Test button with all optional fields."""
        widget = {
            "widget_type": "interactive",
            "extra_data": {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {
                                "type": "button",
                                "label": "Click me",
                                "custom_id": "btn1",
                                "style": "primary",
                                "disabled": False,
                            },
                        ],
                    }
                ]
            },
        }
        check_widget_content(widget)

    def test_interactive_widget_button_invalid_style(self) -> None:
        """Test that button style must be one of the allowed values."""
        widget = {
            "widget_type": "interactive",
            "extra_data": {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {"type": "button", "label": "Click", "style": "invalid_style"},
                        ],
                    }
                ]
            },
        }
        with self.assertRaisesRegex(ValidationError, "Invalid"):
            check_widget_content(widget)

    def test_interactive_widget_select_menu(self) -> None:
        """Test valid select menu component."""
        widget = {
            "widget_type": "interactive",
            "extra_data": {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {
                                "type": "select_menu",
                                "custom_id": "select1",
                                "options": [
                                    {"label": "Option 1", "value": "opt1"},
                                    {"label": "Option 2", "value": "opt2"},
                                ],
                            }
                        ],
                    }
                ]
            },
        }
        check_widget_content(widget)

    def test_interactive_widget_select_menu_with_all_options(self) -> None:
        """Test select menu with all optional fields."""
        widget = {
            "widget_type": "interactive",
            "extra_data": {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {
                                "type": "select_menu",
                                "custom_id": "select1",
                                "options": [
                                    {
                                        "label": "Option 1",
                                        "value": "opt1",
                                        "description": "First option",
                                        "default": True,
                                    },
                                ],
                                "placeholder": "Choose an option",
                                "min_values": 1,
                                "max_values": 1,
                                "disabled": False,
                            }
                        ],
                    }
                ]
            },
        }
        check_widget_content(widget)

    def test_interactive_widget_missing_components(self) -> None:
        """Test that components field is required."""
        widget = {
            "widget_type": "interactive",
            "extra_data": {},
        }
        with self.assertRaisesRegex(ValidationError, "components key is missing"):
            check_widget_content(widget)

    def test_interactive_widget_unknown_component_type(self) -> None:
        """Test that unknown component types are rejected."""
        widget = {
            "widget_type": "interactive",
            "extra_data": {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {"type": "unknown_type", "label": "???"},
                        ],
                    }
                ]
            },
        }
        with self.assertRaisesRegex(ValidationError, "Unknown component type"):
            check_widget_content(widget)

    def test_interactive_widget_missing_button_label(self) -> None:
        """Test that button label is required."""
        widget = {
            "widget_type": "interactive",
            "extra_data": {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {"type": "button", "custom_id": "btn1"},
                        ],
                    }
                ]
            },
        }
        with self.assertRaisesRegex(ValidationError, "label key is missing"):
            check_widget_content(widget)

    def test_interactive_widget_missing_select_custom_id(self) -> None:
        """Test that select menu custom_id is required."""
        widget = {
            "widget_type": "interactive",
            "extra_data": {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {
                                "type": "select_menu",
                                "options": [{"label": "A", "value": "a"}],
                            }
                        ],
                    }
                ]
            },
        }
        with self.assertRaisesRegex(ValidationError, "custom_id key is missing"):
            check_widget_content(widget)


class RichEmbedWidgetValidationTestCase(ZulipTestCase):
    """Tests for rich embed widget validation (Discord-style embeds)."""

    def test_rich_embed_with_title(self) -> None:
        """Test valid rich embed with title."""
        widget = {
            "widget_type": "rich_embed",
            "extra_data": {"title": "My Embed"},
        }
        check_widget_content(widget)

    def test_rich_embed_with_description(self) -> None:
        """Test valid rich embed with description."""
        widget = {
            "widget_type": "rich_embed",
            "extra_data": {"description": "Some description text"},
        }
        check_widget_content(widget)

    def test_rich_embed_with_all_fields(self) -> None:
        """Test rich embed with all optional fields."""
        widget = {
            "widget_type": "rich_embed",
            "extra_data": {
                "title": "My Embed",
                "description": "Description here",
                "url": "https://example.com",
                "color": 0xFF5733,
                "timestamp": "2024-01-15T10:30:00Z",
                "footer": {"text": "Footer text", "icon_url": "https://example.com/icon.png"},
                "thumbnail": {"url": "https://example.com/thumb.png"},
                "image": {"url": "https://example.com/image.png"},
                "author": {
                    "name": "Author Name",
                    "url": "https://author.example.com",
                    "icon_url": "https://example.com/author.png",
                },
                "fields": [
                    {"name": "Field 1", "value": "Value 1", "inline": True},
                    {"name": "Field 2", "value": "Value 2"},
                ],
            },
        }
        check_widget_content(widget)

    def test_rich_embed_requires_title_or_description(self) -> None:
        """Test that rich embed requires at least title or description."""
        widget = {
            "widget_type": "rich_embed",
            "extra_data": {"color": 0xFF5733},
        }
        with self.assertRaisesRegex(ValidationError, "requires at least title or description"):
            check_widget_content(widget)

    def test_rich_embed_field_missing_name(self) -> None:
        """Test that embed fields require name."""
        widget = {
            "widget_type": "rich_embed",
            "extra_data": {
                "title": "Test",
                "fields": [{"value": "Some value"}],
            },
        }
        with self.assertRaisesRegex(ValidationError, "name key is missing"):
            check_widget_content(widget)

    def test_rich_embed_field_missing_value(self) -> None:
        """Test that embed fields require value."""
        widget = {
            "widget_type": "rich_embed",
            "extra_data": {
                "title": "Test",
                "fields": [{"name": "Field name"}],
            },
        }
        with self.assertRaisesRegex(ValidationError, "value key is missing"):
            check_widget_content(widget)

    def test_rich_embed_footer_missing_text(self) -> None:
        """Test that footer requires text."""
        widget = {
            "widget_type": "rich_embed",
            "extra_data": {
                "title": "Test",
                "footer": {"icon_url": "https://example.com/icon.png"},
            },
        }
        with self.assertRaisesRegex(ValidationError, "text key is missing"):
            check_widget_content(widget)

    def test_rich_embed_author_missing_name(self) -> None:
        """Test that author requires name."""
        widget = {
            "widget_type": "rich_embed",
            "extra_data": {
                "title": "Test",
                "author": {"url": "https://example.com"},
            },
        }
        with self.assertRaisesRegex(ValidationError, "name key is missing"):
            check_widget_content(widget)
