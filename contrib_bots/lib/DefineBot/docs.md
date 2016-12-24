# DictBot

This is a bot that defines a word that the user inputs.
Whenever the user inputs a message starting with '@define',The bot defines the 
word that follows.

The definitions are brought to the website using an API.The bot posts the 
definition of the word to the stream from which the user inputs the message.
If the user inputs a word that does not exist or a word that is incorrect,
the definition is not displayed.

For example, if the user says "@define crash", all the meanings of crash
appears,like,"(noun)..." or "(verb)..." If the user enters a wrong word,
like "@define cresh" or "@define crish",then an error message saying no
definition is available is displayed.

![Correct Word](correct_word.png)
![Wrong Word](wrong_word.png)