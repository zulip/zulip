class BotCommandRegistry(object):
    def __init__(self, about_text, just_mentioned=-1):
        # Note the values are empty, since they are handled elsewhere
        self._commands = \
            {'help'    : ('','output this help text'),
             'commands': ('','briefly list these supported commands'),
             'about'   : ('','tells you what this bot is intended to do'),
            }
        self._about_text = about_text
        self._just_mentioned = just_mentioned
      
    def usage(self):
        return '''
            This generic zulip bot is intended to be a simple extensible design
            which relies upon users simply adding in extra elements into a dict.
            '''
    def add_command(self,cmd,text_or_function,explanation):
        if cmd not in self._commands.keys():
            self._commands[cmd] = (text_or_function,explanation)
        else:
            print("WARNING: %s command already exists, so haven't added it." % cmd)

    def handle_message(self, message, client, state_handler):
        msg = self._about_text

        content = message['content']
        if len(content) == 0:
            if self._just_mentioned != -1:
                if not isinstance(self._just_mentioned,str):
                    msg = self._just_mentioned()
                else:
                    msg = self._just_mentioned
                content = "about" # Use pass-through below
            else:
                content = "help" # Default handling of just mentioning bot
            
        command = content.split()[0].strip()
        args = content.split()[1:]

        if command == 'about':
            pass # defaults to about text
        elif command == 'help':
            for key,value in self._commands.items(): msg += "  \n"+key+" : "+value[1]
        elif command == 'commands':
            msg = "Commands: "+(" ".join(self._commands.keys()))
        elif command in self._commands.keys():
            if not isinstance(self._commands[command][0],str): 
                msg = self._commands[command][0](args)
            else:
                msg = self._commands[command][0]
        else:
            msg = "Sorry, I don't understand that command. Please try one of the following.\n"
            msg += "Commands: "+(" ".join(self._commands.keys()))

        client.send_reply(message, msg)

import time
class DemoHandler(BotCommandRegistry):
    def __init__(self):
        BotCommandRegistry.__init__(self, \
          'A Generic zulip bot that you can extend using a dictionary',
          'Try typing "commands" for the list of commands.'
#          -1 # Default => just mentioning leads to help text
          )

        # This will do nothing (help command already exists)
        self.add_command('help','help','help')

        # Examples of text, function, and function which uses arguments
        self.add_command('dance','/me dances','makes me dance!')
        self.add_command('go',lambda x : ("I live here!" if " ".join(x)=="away" else "where?"),"where should I go?")
        self.add_command('time',lambda x : time.time(),'time since the epoch')

handler_class = DemoHandler
