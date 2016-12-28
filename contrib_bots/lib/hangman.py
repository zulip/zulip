# -*- coding: utf-8 -*-
from __future__ import absolute_import
import requests
from six.moves import range


class HangmanHandler(object):
    def usage(self):
        return '''
    This bot allows users to play Hangman in streams that the Hangman
    bot is subscribed to using the following simple commands:
    - @hangman new: This command starts a new Hangman game.
    - @hangman guess <letter>: This command lets the user
    guess a letter for the current Hangman game.
    - @hangman stop: This command stops the current Hangman game.
    - @hangman help: This command gives users information
    about the Hangman bot.
    '''

    def triage_message(self, message, client):
        # Return True if we want to (possibly) respond to this message
        original_content = message['content']
        is_hangman_command = original_content.lower().startswith('@hangman ')

        return is_hangman_command

    def get_new_word(bot_self):
        link = "http://www.setgetgo.com/randomword/get.php"
        if not hasattr(bot_self, 'currentword'):
            try:
                bot_self.currentword = requests.get(link).text
                bot_self.output = "To start guessing letters, type `@hangman" \
                    " guess <letter>`. Good luck!\n\n```" \
                    "" + "  ".join("_" * len(bot_self.currentword)) + "```"
                bot_self.stage = 0
                bot_self.guessed = []
            except:
                bot_self.output = "Could not generate a word at this moment." \
                    " Try again later."
        else:
            if len(bot_self.currentword) == 0:
                bot_self.currentword = requests.get(link).text
                bot_self.output = "To start guessing letters, " \
                    "type `@hangman guess <letter>`. Good luck!\n\n```" \
                    "" + "  ".join("_" * len(bot_self.currentword)) + "```"
                bot_self.stage = 0
                bot_self.guessed = []
            else:
                bot_self.output = "There is already a game of hangman " \
                    "active! To stop the current game, type `@hangman stop`."

    def process_guess(bot_self, message):
        end = ""
        bot_self.ended = False
        split = message.strip().split(" ")
        if len(split) == 2:
            bot_self.output = "You forgot to guess a letter! " \
                "To guess again, type `@hangman guess <letter>`."
        elif len(split) > 3:
            bot_self.output = "You are supposed to guess one letter " \
                "at a time, not multiple words at once!" \
                " To guess again, type `@hangman guess <letter>`."
        elif len(split[2]) > 1:
            bot_self.output = "You are supposed to guess a letter, " \
                "not a word! To guess again, type `@hangman guess <letter>`."
        elif split[2] in bot_self.guessed:
            bot_self.output = "You have already guessed the letter " \
                "" + split[2] + "! To guess again, type " \
                "`@hangman guess <letter>`."
        elif split[2] not in "abcdefghijklmnopqrstuvwxyz":
            bot_self.output = split[2] + " is not a letter! To guess a " \
                "letter, type `@hangman guess <letter>`."
        else:
            bot_self.guessed.append(split[2])
            if split[2] not in bot_self.currentword:
                bot_self.stage += 1
                if bot_self.stage == 10:
                    end = "\n\n:crying_cat_face: Oh no, you lost! The " \
                        "correct word was " + str(bot_self.currentword) + "." \
                          " To play again, type `@hangman new`."
                    bot_self.ended = True
            stages = ["```", "```\n=============",
                      ("```\n           |\n           |\n           |" +
                       "\n           |\n           |\n============="),
                      ("```\n   +-------+\n           |\n           |\n     " +
                       "      |\n           |\n           |\n============="),
                      ("```\n   +-------+\n   |       |\n           |\n     " +
                       "      |\n           |\n           |\n============="),
                      ("```\n   +-------+\n   |       |\n   0       |\n     " +
                       "      |\n           |\n           |\n============="),
                      ("```\n   +-------+\n   |       |\n   0       |\n   | " +
                       "      |\n           |\n           |\n============="),
                      ("```\n   +-------+\n   |       |\n   0       |\n  /| " +
                       "      |\n           |\n           |\n============="),
                      ("```\n   +-------+\n   |       |\n   0       |\n  /|" +
                       "\      |\n           |\n           |\n============="),
                      ("```\n   +-------+\n   |       |\n   0       |\n  /|" +
                       "\      |\n  /        |\n           |\n============="),
                      ("```\n   +-------+\n   |       |\n   0       |\n  /|" +
                       "\      |\n  / \      |\n           |\n=============")]
            outcur = []
            wrongguess = []
            for i, current_word in enumerate(bot_self.currentword):
                if bot_self.currentword[i] in bot_self.guessed:
                    outcur.append(str(bot_self.currentword[i]))
                else:
                    outcur.append("_")
            if "_" not in outcur:
                end = "\n\n:party_popper: Congratulations! You won! " \
                    "To play again, type @hangman new. :party_popper:"
                bot_self.ended = True
            for i, guessed_word in enumerate(bot_self.guessed):
                if bot_self.guessed[i] not in bot_self.currentword:
                    wrongguess.append(str(bot_self.guessed[i]))
            bot_self.output = (stages[bot_self.stage] + "\n```\n\n```" +
                               "  ".join(outcur) + "```\n\n```Wrong guesses:" +
                               " " + ", ".join(wrongguess) + "```" + end)

    def handle_message(self, message, client, state_handler):
        original_content = message['content'].lower()
        original_content_split = original_content.split(" ")
        if original_content_split[1] == "new":
            self.get_new_word()
        elif original_content_split[1] == "guess":
            if not hasattr(self, 'currentword'):
                self.output = "There is currently no Hangman game " \
                    " active! To start a new game, type @hangman new."
            else:
                self.process_guess(original_content)
                if self.ended:
                    del self.currentword
        elif original_content_split[1] == "help":
            self.output = "This bot allows users to play Hangman " \
                "in streams that the Hangman bot is subscribed to" \
                " using the following simple commands:" \
                "\n- `@hangman new`: This command starts a new Hangman game." \
                "\n- `@hangman guess <letter>`: This command lets the " \
                "user guess a letter for the current Hangman game." \
                "\n- `@hangman stop`: This command stops" \
                " the current Hangman game." \
                "\n- `@hangman help`: This command gives users" \
                " information about the Hangman bot."
        elif original_content_split[1] == "stop":
            if not hasattr(self, 'currentword'):
                self.output = "There is currently no Hangman game " \
                    "active! To start a new game, type `@hangman new`."
            else:
                self.output = "The current game of Hangman has ended!" \
                    " The correct word was " + self.currentword + "."
                del self.currentword
        else:
            self.output = original_content_split[1] + " is not a " \
                "valid command! For a list of commands type `@hangman help`"
        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=self.output,
        ))

handler_class = HangmanHandler
