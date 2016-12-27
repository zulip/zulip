# -*- coding: utf-8 -*-
import requests

def get_new_word(inp):
    try:
        inp.currentword
    except AttributeError:
        inp.currentword = requests.get("http://www.setgetgo.com/randomword/get.php").text
        inp.output = "To start guessing letters, type @hangman guess <letter>. Good luck!\n·\n```" + "  ".join("_" * len(inp.currentword)) + "```"
        inp.stage = 0
        inp.guessed = []
    else:
        if len(inp.currentword) == 0:
            inp.currentword = requests.get("http://www.setgetgo.com/randomword/get.php").text
            inp.output = "To start guessing letters, type @hangman guess <letter>. Good luck!\n·\n```" + "  ".join("_" * len(inp.currentword)) + "```"
            inp.stage = 0
            inp.guessed = []
        else:
            inp.output = "There is already a game of hangman active! To stop the current game, type @hangman stop." 
    return inp

def process_guess(message, self):
    end = ""
    self.ended = False
    split = message.strip().split(" ")
    if len(split) == 2:
        self.output = "You forgot to guess a letter! To guess again, type @hangman guess <letter>."
    elif len(split) > 3:
        self.output = "You are supposed to guess one letter at a time, not multiple words at once! To guess again, type @hangman guess <letter>."
    elif len(split[2]) > 1:
        self.output = "You are supposed to guess a letter, not a word! To guess again, type @hangman guess <letter>."
    elif split[2] in self.guessed:
        self.output = "You have already guessed the letter " + split[2] + "! To guess again, type @hangman guess <letter>."
    else:
        self.guessed.append(split[2])
        if split[2] not in self.currentword:
            self.stage += 1
            if(self.stage==10):
                end = "\n·\n:crying_cat_face: Oh no, you lost! The correct word was " + str(self.currentword) + ". To play again, type @hangman new."
                self.ended = True
        stages = ["","·\n·\n·\n·\n·\n·\n=========","·\n···············|\n···············|\n···············|\n···············|\n···············|\n=========",
                  "······+-----+\n···············|\n···············|\n···············|\n···············|\n···············|\n=========",
                  "······+-----+\n······|········|\n···············|\n···············|\n···············|\n···············|\n=========",
                  "······+-----+\n······|········|\n······0·······|\n···············|\n···············|\n···············|\n=========",
                  "······+-----+\n······|········|\n······0·······|\n······|·······|\n··············|\n···············|\n=========",
                  "······+-----+\n······|········|\n······0·······|\n·····/|········|\n···············|\n···············|\n=========",
                  "······+-----+\n······|········|\n······0·······|\n·····/|\······|\n···············|\n···············|\n=========",
                  "······+-----+\n······|········|\n······0·······|\n·····/|\······|\n·····/·········|\n···············|\n=========",
                  "······+-----+\n······|········|\n······0·······|\n·····/|\······|\n·····/ \······|\n···············|\n========="]
        outcur = []
        wrongguess = []
        for i in range(0, len(self.currentword)):
            if self.currentword[i] in self.guessed:
                outcur.append(str(self.currentword[i]))
            else:
                outcur.append("_")
        if "_" not in outcur:
            end = "\n·\n:party_popper: Congratulations! You won! To play again, type @hangman new. :party_popper:"
            self.ended = True
        for i in range(0, len(self.guessed)):
            if self.guessed[i] not in self.currentword:
                wrongguess.append(str(self.guessed[i]))
        self.output = stages[self.stage] + "\n·\n```" + "  ".join(outcur) + "```\n·\n```Wrong guesses: " + ", ".join(wrongguess) + "```" + end
            
    return self

class hangmanHandler(object):
    def usage(self):
        return '''
    This bot allows users to play hangman in streams that the hangman bot is subscribed to using the following simple commands:
    - @hangman new: This command starts a new hangman game.
    - @hangman guess <letter>: This command lets the user guess a letter for the current hangman game.
    - @hangman stop: This command stops the current hangman game.
    - @hangman help: This command gives users information about the hangman bot.
    '''

    def triage_message(self, message):
        # Return True if we want to (possibly) respond to this message
        original_content = message['content']
        is_hangman_command = original_content.lower().startswith('@hangman ')

        return is_hangman_command

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_content_split = original_content.split(" ")
        if original_content_split[1] == "new":
            self = get_new_word(self)
            print(self.currentword)
        elif original_content_split[1] == "guess":
            try:
                self.currentword
            except AttributeError:
                self.output = "There is currently not a game of hangman active! To start a new game, type @hangman new."
            else:
                self = process_guess(original_content.lower(), self)
                if self.ended:
                    del self.currentword
        elif original_content_split[1] == "help":
            self.output = "This bot allows users to play hangman in streams that the hangman bot is subscribed to using the following simple commands:\n- @hangman new: This command starts a new hangman game.\n- @hangman guess <letter>: This command lets the user guess a letter for the current hangman game.\n- @hangman stop: This command stops the current hangman game.\n- @hangman help: This command gives users information about the hangman bot."
        elif original_content_split[1] == "stop":
            try:
                self.currentword
            except AttributeError:
                self.output = "There is currently not a game of hangman active! To start a new game, type @hangman new."
            else:
                self.output = "The current game of hangman has ended! The correct word was " + self.currentword + "."
                del self.currentword
        else:
            self.output = original_content_split[1] + " is not a valid command! For a list of commands type @hangman help"

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=self.output,
        ))


handler_class = hangmanHandler
