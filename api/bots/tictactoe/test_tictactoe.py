#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

from bots_test_lib import BotTestCase
from bot_lib import StateHandler

class TestTictactoeBot(BotTestCase):
    bot_name = "tictactoe"

    def test_bot(self):
        messages = [  # Template for message inputs to test, absent of message content
            {
                'type': 'stream',
                'display_recipient': 'some stream',
                'subject': 'some subject',
                'sender_email': 'foo_sender@zulip.com',
            },
            {
                'type': 'private',
                'sender_email': 'foo_sender@zulip.com',
            },
        ]
        private_response = {
            'type': 'private',
            'to': 'foo_sender@zulip.com',
            'subject': 'foo_sender@zulip.com',  # FIXME Requiring this in bot is a bug?
        }

        help_txt = "*Help for Tic-Tac-Toe bot* \nThe bot responds to messages starting with @mention-bot.\n**@mention-bot new** will start a new game (but not if you're already in the middle of a game). You must type this first to start playing!\n**@mention-bot help** will return this help function.\n**@mention-bot quit** will quit from the current game.\n**@mention-bot <coordinate>** will make a move at the given coordinate.\nCoordinates are entered in a (row, column) format. Numbering is from top to bottom and left to right. \nHere are the coordinates of each position. (Parentheses and spaces are optional). \n(1, 1)  (1, 2)  (1, 3) \n(2, 1)  (2, 2)  (2, 3) \n(3, 1) (3, 2) (3, 3) \n"
        didnt_understand_txt = "Hmm, I didn't understand your input. Type **@tictactoe help** or **@ttt help** to see valid inputs."
        new_game_txt = "Welcome to tic-tac-toe! You'll be x's and I'll be o's. Your move first!\nCoordinates are entered in a (row, column) format. Numbering is from top to bottom and left to right.\nHere are the coordinates of each position. (Parentheses and spaces are optional.) \n(1, 1)  (1, 2)  (1, 3) \n(2, 1)  (2, 2)  (2, 3) \n(3, 1) (3, 2) (3, 3) \n Your move would be one of these. To make a move, type @mention-bot followed by a space and the coordinate."

        expected_send_message = [
            ("", didnt_understand_txt),
            ("help", help_txt),
            ("quit", didnt_understand_txt),  # Quit not understood when no game
            ("new", new_game_txt),
            ("quit", "You've successfully quit the game."),  # If have state
            ("quit", didnt_understand_txt),  # Quit not understood when no game
        ]
        for m in messages:
            state = StateHandler()
            for (mesg, resp) in expected_send_message:
                self.assert_bot_response(dict(m, content=mesg),
                                         dict(private_response, content=resp),
                                         'send_message', state)
