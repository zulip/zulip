class SimpleExtensibleHandler(object):
    def __init__(self, help_text, just_mentioned=-1):
        self._commands = {'help':'',
                       'commands':'',
               }
        self._help_text = help_text
        self._just_mentioned = just_mentioned
      
    def usage(self):
        return '''
            This generic zulip bot is intended to be a simple extensible design
            which relies upon users simply adding in extra elements into a dict.
            '''
    def add_command(self,cmd,text):
        if cmd not in self._commands:
            self._commands[cmd] = text

    def handle_message(self, message, client, state_handler):
        content = message['content'].strip()

        if len(content) == 0:
            client.send_reply(message, self._just_mentioned)
        elif content == 'help':
            client.send_reply(message, self._help_text)
        elif content == 'commands':
            client.send_reply(message, "Commands: "+(" ".join(self._commands.keys())))
        elif content in self._commands.keys():
            if not isinstance(self._commands[content],str): 
                client.send_reply(message, self._commands[content](content))
            else:
                client.send_reply(message, self._commands[content]) 

import time
class DemoHandler(SimpleExtensibleHandler):
    def __init__(self):
        SimpleExtensibleHandler.__init__(self, "help text")
        self.add_command('about','A Generic zulip bot that you can extend using a dictionary')
        self.add_command('dance','/me dances')
        self.add_command('time',lambda x: time.time())

handler_class = DemoHandler
