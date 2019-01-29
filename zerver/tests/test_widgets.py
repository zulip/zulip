import ujson

from typing import Dict, Any

from zerver.models import SubMessage

from zerver.lib.test_classes import ZulipTestCase

from zerver.lib.widget import get_widget_data

from zerver.lib.validator import check_widget_content

class WidgetContentTestCase(ZulipTestCase):
    def test_validation(self) -> None:
        def assert_error(obj: object, msg: str) -> None:
            self.assertEqual(check_widget_content(obj), msg)

        assert_error(5,
                     'widget_content is not a dict')

        assert_error({},
                     'widget_type is not in widget_content')

        assert_error(dict(widget_type='whatever'),
                     'extra_data is not in widget_content')

        assert_error(dict(widget_type='zform', extra_data=4),
                     'extra_data is not a dict')

        assert_error(dict(widget_type='bogus', extra_data={}),
                     'unknown widget type: bogus')

        extra_data = dict()  # type: Dict[str, Any]
        obj = dict(widget_type='zform', extra_data=extra_data)

        assert_error(obj, 'zform is missing type field')

        extra_data['type'] = 'bogus'
        assert_error(obj, 'unknown zform type: bogus')

        extra_data['type'] = 'choices'
        assert_error(obj, 'heading key is missing from extra_data')

        extra_data['heading'] = 'whatever'
        assert_error(obj, 'choices key is missing from extra_data')

        extra_data['choices'] = 99
        assert_error(obj, 'extra_data["choices"] is not a list')

        extra_data['choices'] = [99]
        assert_error(obj, 'extra_data["choices"][0] is not a dict')

        extra_data['choices'] = [
            dict(long_name='foo', reply='bar'),
        ]
        assert_error(obj, 'short_name key is missing from extra_data["choices"][0]')

        extra_data['choices'] = [
            dict(short_name='a', long_name='foo', reply='bar'),
        ]

        self.assertEqual(check_widget_content(obj), None)

    def test_message_error_handling(self) -> None:
        sender_email = self.example_email('cordelia')
        stream_name = 'Verona'

        payload = dict(
            type="stream",
            to=stream_name,
            sender=sender_email,
            client='test suite',
            topic='whatever',
            content='whatever',
        )

        payload['widget_content'] = '{{{{{{'  # unparsable
        result = self.api_post(sender_email, "/api/v1/messages", payload)
        self.assert_json_error_contains(result, 'Widgets: API programmer sent invalid JSON')

        bogus_data = dict(color='red', foo='bar', x=2)
        payload['widget_content'] = ujson.dumps(bogus_data)
        result = self.api_post(sender_email, "/api/v1/messages", payload)
        self.assert_json_error_contains(result, 'Widgets: widget_type is not in widget_content')

    def test_get_widget_data_for_non_widget_messages(self) -> None:
        # This is a pretty important test, despite testing the
        # "negative" case.  We never want widgets to interfere
        # with normal messages.

        test_messages = [
            '',
            '     ',
            'this is an ordinary message',
            '/bogus_command',
            '/me shrugs',
            'use /poll',
        ]

        for message in test_messages:
            self.assertEqual(get_widget_data(content=message), (None, None))

        # Add a positive check for context
        self.assertEqual(get_widget_data(content='/tictactoe'), ('tictactoe', None))

    def test_explicit_widget_content(self) -> None:
        # Users can send widget_content directly on messages
        # using the `widget_content` field.

        sender_email = self.example_email('cordelia')
        stream_name = 'Verona'
        content = 'does-not-matter'
        zform_data = dict(
            type='choices',
            heading='Options:',
            choices=[],
        )

        widget_content = ujson.dumps(
            dict(
                widget_type='zform',
                extra_data=zform_data,
            ),
        )

        payload = dict(
            type="stream",
            to=stream_name,
            sender=sender_email,
            client='test suite',
            topic='whatever',
            content=content,
            widget_content=widget_content,
        )
        result = self.api_post(sender_email, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="zform",
            extra_data=zform_data,
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, 'widget')
        self.assertEqual(ujson.loads(submessage.content), expected_submessage_content)

    def test_tictactoe(self) -> None:
        # The tictactoe widget is mostly useful as a code sample,
        # and it also helps us get test coverage that could apply
        # to future widgets.

        sender_email = self.example_email('cordelia')
        stream_name = 'Verona'
        content = '/tictactoe'

        payload = dict(
            type="stream",
            to=stream_name,
            sender=sender_email,
            client='test suite',
            topic='whatever',
            content=content,
        )
        result = self.api_post(sender_email, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="tictactoe",
            extra_data=None,
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, 'widget')
        self.assertEqual(ujson.loads(submessage.content), expected_submessage_content)

    def test_poll_command_extra_data(self) -> None:
        sender_email = self.example_email('cordelia')
        stream_name = 'Verona'
        # We test for both trailing and leading spaces, along with blank lines
        # for the poll options.
        content = '/poll What is your favorite color?\n\nRed\nGreen  \n\n   Blue\n - Yellow'

        payload = dict(
            type="stream",
            to=stream_name,
            sender=sender_email,
            client='test suite',
            topic='whatever',
            content=content,
        )
        result = self.api_post(sender_email, "/api/v1/messages", payload)
        self.assert_json_success(result)

        message = self.get_last_message()
        self.assertEqual(message.content, content)

        expected_submessage_content = dict(
            widget_type="poll",
            extra_data=dict(
                options=['Red', 'Green', 'Blue', 'Yellow'],
                question="What is your favorite color?",
            ),
        )

        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, 'widget')
        self.assertEqual(ujson.loads(submessage.content), expected_submessage_content)

        # Now don't supply a question.

        content = '/poll'
        payload['content'] = content
        result = self.api_post(sender_email, "/api/v1/messages", payload)
        self.assert_json_success(result)

        expected_submessage_content = dict(
            widget_type="poll",
            extra_data=dict(
                options=[],
                question='',
            ),
        )

        message = self.get_last_message()
        self.assertEqual(message.content, content)
        submessage = SubMessage.objects.get(message_id=message.id)
        self.assertEqual(submessage.msg_type, 'widget')
        self.assertEqual(ujson.loads(submessage.content), expected_submessage_content)
