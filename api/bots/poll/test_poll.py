#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

from collections import OrderedDict

from bots_test_lib import BotTestCase

class TestPollBot(BotTestCase):
    bot_name = "poll"

    def test_bot(self):

        test_email  = "sender@realm.com"
        test_stream = "test stream"
        test_topic  = "test topic"

        private_msg_template = dict(type='private', to=test_email)
        poll_msg_template = dict(type='stream', to=test_stream, subject=test_topic)

        # Simple commands
        # These are accepted anywhere, but private messages are sent to the sender

        about_multiline = '''
        This bot maintains up to one poll per user, per topic, in streams only.
        It currently keeps a running count of the votes, as they are made, with one
        mesage in the stream being updated to show the current status.
        Message the bot privately, appending the stream and topic, or mention it
        within a topic (for new, vote and end commands); if the stream or topic contain spaces use a
        '+' where the space would be.
        '''

        about_txt = " ".join(about_multiline.split())
        commands_txt = "Commands: about, help, commands, new, vote, end"
        extended_commands_multiline = '''\n\nIt supports the following commands:\n\n**about** : gives a simple summary of this bot.\n**help** : produces this help.\n**commands** : a concise form of help, listing the supported commands.\n**new** : start a new poll: specify a title on the following line and at least two options on subsequent lines.\n**vote** : vote in an ongoing poll: specify a poll id given in the poll message followed by the number of the option to vote for.\n**end** : end your own ongoing poll.'''
        help_txt = about_txt + extended_commands_multiline
        simple_map = OrderedDict([
            ("", help_txt),
            ("about", about_txt),
            ("help", help_txt),
            ("commands", commands_txt),
        ])
        expected_simple = OrderedDict([(k, dict(private_msg_template, content=v))
                                       for k, v in simple_map.items()])
        self.check_expected_responses(expected_simple, expected_method='send_message',
                                      email=test_email, type='all')

        # Complex commands

        error_msg = {
            'new': ("To start a new poll: specify a title on the following line "
                    "and at least two options on subsequent lines."),
            'vote': ("To vote in an ongoing poll: specify a poll id given in the "
                     "poll message followed by the number of the option to vote for."),
            'end': ("You do not have a poll in '#test stream' and topic 'test topic'"),
        }
        poll_lines = ["Please select from one of the following options:",
                      "Something great", "Something not so great", "This is bad"]
        private_msg = "\nPlease specify a stream & topic if messaging the bot privately."

        ## First do tests for cases that don't generate a poll and should fail with just
        ## a private error message

        def test_fails(src_location):
            s = t = ""  # These need to be specified if src_location is private
            recipient = test_stream
            if src_location == 'private':
                (s, t) = (" "+test_stream.replace(" ", "+"), " "+test_topic.replace(" ", "+"))
                recipient = test_email
            st = (src_location == 'stream')
            # Note that if stream & topic are "" then some of these entries are overwritten
            expected_ = OrderedDict([
                ('new', error_msg['new'] if st else private_msg),
                ('new' + s, error_msg['new'] if st else private_msg),
                ('new' + s + t + t, error_msg['new'] if st else private_msg),
                ('new' + s + t + "\n", error_msg['new']),
                ('new' + s + t + "\n" + poll_lines[0], error_msg['new']),
                ('new' + s + t + "\n" + poll_lines[0] + "\n", error_msg['new']),
                ('new' + s + t + "\n" + poll_lines[0] + "\n" + poll_lines[1], error_msg['new']),
                ('new' + s + t + "\n" + poll_lines[0] + "\n" + poll_lines[1] + "\n", error_msg['new']),
                ('vote', error_msg['vote'] if st else error_msg['vote']+private_msg),
                ('vote' + s, error_msg['vote'] if st else error_msg['vote']+private_msg),
                ('vote' + s + t + t, error_msg['vote'] if st else error_msg['vote']+private_msg),
                ('vote' + s + t + " 5", error_msg['vote'] if st else error_msg['vote']+private_msg),
                ('vote' + s + t + " 5" + " 1", error_msg['vote']),  # no poll, so fails
                ('end', error_msg['end'] if st else private_msg),
                ('end' + s, error_msg['end'] if st else private_msg),
                ('end' + s + t, error_msg['end']),  # no poll, so fails
            ])
            # Convert table above into expectation dict with templated messages
            expected = OrderedDict([(k, dict(private_msg_template, content=v))
                                    for k, v in expected_.items()])
            self.check_expected_responses(expected, expected_method='send_message',
                                          email=test_email, type=src_location,
                                          recipient=recipient, subject='test topic')

        # Test messages from within a stream/topic
        test_fails('stream')
        # Test messages sent privately
        test_fails('private')

        ## Now test the stateful poll generation, voting and poll ending
        ## This depends on functional
        ## - dual-posting support (poll-bot may update the poll message and
        ##   always sends a private message stating what has happened)
        ## - message update support
        ## FIXME Both of these are currently lacking in the test framework

        poll_message = "Poll created in stream '#test stream' with topic 'test topic':\nPoll by Foo Bar (id: 0)\nPlease select from one of the following options:\n1. [0] Something great\n2. [0] Something not so great\n3. [0] This is bad\n"

        def test_polls(src_location):
            s = t = ""  # These need to be specified if src_location is private
            recipient = test_stream
            if src_location == 'private':
                (s, t) = (" "+test_stream.replace(" ", "+"), " "+test_topic.replace(" ", "+"))
                recipient = test_email
            st = (src_location == 'stream')
            expected_ = OrderedDict([
                ('new' + s + t + "\n" + "\n".join(poll_lines), poll_message),
            ])
            # Convert table above into expectation dict with templated messages
            expected = OrderedDict([(k, dict(private_msg_template, content=v))
                                    for k, v in expected_.items()])
            self.check_expected_responses(expected, expected_method='send_message',
                                          email=test_email, type=src_location,
                                          recipient=recipient, subject=test_topic)

            expected_ = OrderedDict([
                ('new' + s + t + "\n" + "\n".join(poll_lines), poll_message),
            ])
            # Convert table above into expectation dict with templated messages
            expected = OrderedDict([(k, dict(poll_msg_template, content=v))
                                    for k, v in expected_.items()])
            self.check_expected_responses(expected, expected_method='send_message',
                                          email=test_email, type=src_location,
                                          recipient=recipient, subject=test_topic)

#        if 1: print("Testing poll usage from a stream")
#        test_polls('stream')
#        if 1: print("Testing poll usage from a private message")
#        test_polls('private')
