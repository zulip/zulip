import json
import os
import sys

from random import choice

try:
    from chatterbot import ChatBot
    from chatterbot.trainers import ChatterBotCorpusTrainer, ListTrainer
except ImportError:
    raise ImportError("""It looks like you are missing chatterbot.
                      Please: pip install chatterbot""")

CONTRIB_BOTS_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.dirname(CONTRIB_BOTS_DIR))
sys.path.insert(0, os.path.dirname(CONTRIB_BOTS_DIR))

JOKES_PATH = os.path.join(CONTRIB_BOTS_DIR, 'assets/var/jokes.json')
DATABASE_PATH = os.path.join(CONTRIB_BOTS_DIR, 'assets/var/database.db')
DIRECTORY_PATH = os.path.join(CONTRIB_BOTS_DIR, 'assets')
VAR_PATH = os.path.join(CONTRIB_BOTS_DIR, 'assets/var')

if not os.path.exists(DIRECTORY_PATH):
    os.makedirs(DIRECTORY_PATH)

if not os.path.exists(VAR_PATH):
    os.makedirs(VAR_PATH)

# Create a new instance of a ChatBot
def create_chat_bot(no_learn):
    return ChatBot("John",
                   storage_adapter="chatterbot.storage.JsonFileStorageAdapter",
                   logic_adapters=
                   [
                       "chatterbot.logic.MathematicalEvaluation",
                       {
                           "import_path": "chatterbot.logic.BestMatch",
                           "response_selection_method": "chatterbot.response_selection.get_random_response",
                           "statement_comparison_function": "chatterbot.comparisons.levenshtein_distance"
                       }],
                   output_adapter="chatterbot.output.OutputAdapter",
                   output_format='text',
                   database=DATABASE_PATH,
                   silence_performance_warning="True",
                   read_only=no_learn)

bot = create_chat_bot(False)
bot.set_trainer(ListTrainer)

bot.train([
    "I want to contribute",
    """Contributors are more than welcomed! Please read
    https://github.com/zulip/zulip#how-to-get-involved-with-contributing-to-zulip
    to learn how to contribute.""",
])

bot.train([
    "What is Zulip?",
    """Zulip is a powerful, open source group chat application. Written in Python
    and using the Django framework, Zulip supports both private messaging and group
    chats via conversation streams. You can learn more about the product and its
    features at https://www.zulip.org.""",
])

bot.train([
    "I would like to request a remote dev instance",
    """Greetings! You should receive a response from one of our mentors soon.
    In the meantime, why don't you learn more about running Zulip on a development
    environment? https://zulip.readthedocs.io/en/latest/using-dev-environment.html""",
])

bot.train([
    "Joke!",
    "Only if you ask nicely!",
])

bot.train([
    "What is your name?",
    "I am John, my job is to assist you with Zulip.",
])

bot.train([
    "What can you do?",
    "I can provide useful information and jokes if you follow etiquette.",
])

with open(JOKES_PATH) as data_file:
    for joke in json.load(data_file):
        bot.train([
            "Please can you tell me a joke?",
            joke['joke'],
        ])

bot.set_trainer(ChatterBotCorpusTrainer)

bot.train(
    "chatterbot.corpus.english"
)

bota = create_chat_bot(True)

class JohnHandler(object):
    '''
    This bot aims to be Zulip's virtual assistant. It
    finds the best match from a certain input.
    Also understands the English language and can
    mantain a conversation, joke and give useful information.
    '''

    def usage(self):
        return '''
            This bot aims to be Zulip's virtual assistant. It
            finds the best match from a certain input.
            Also understands the English language and can
            mantain a conversation, joke and give useful information.
            '''

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        bot_response = str(bota.get_response(original_content))

        if message['type'] == 'private':
            client.send_message(dict(
                type='private',
                to=message['sender_email'],
                content=bot_response,
            ))
        else:
            client.send_message(dict(
                type='stream',
                to=message['display_recipient'],
                subject=message['subject'],
                content=bot_response,
            ))

handler_class = JohnHandler
