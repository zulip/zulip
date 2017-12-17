I ran into only one problem.This problem is about permissions of the file
zuliprc,which contains all the info about the API key and etc. 

The error looked like this..
  
  ```$ zulip-run-bot helloworld --config-file ~/zuliprc-my-bot
  Traceback (most recent call last):
  File "C:\Users\new\python-zulip-api\zulip-api-py3-venv\Scripts\zulip-run-bot-script.py", line 11, in <module>
  load_entry_point('zulip-bots', 'console_scripts', 'zulip-run-bot')()
  File "c:\users\new\python-zulip-api\zulip_bots\zulip_bots\run.py", line 143, in main
  bot_name=bot_name
  File "c:\users\new\python-zulip-api\zulip_bots\zulip_bots\lib.py", line 262, in run_message_handler_for_bot
  client = Client(config_file=config_file, client=client_name)
  File "c:\users\new\python-zulip-api\zulip\zulip\__init__.py", line 311, in __init__
  with open(config_file, 'r') as f:
  PermissionError: [Errno 13] Permission denied: 'C:\\Users\\new\\zuliprc-my-bot'
  (zulip-api-py3-venv)
  ```
  
  This just shows that the file cant be accessed.
  I checked out the Permissions in the Properties,everything was fine there.
  The error is that I gave the path to my bot's key not the key itself!!
  We need to give the file not the directory it is located in.
