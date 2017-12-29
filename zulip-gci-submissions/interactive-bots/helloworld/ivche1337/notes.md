I ran into an issue when i tried to run the bot like this:
    $ zulip-run-bot ivche_helloworld_bot --config-file ~/zuliprc-my-bot

I got this error:

Traceback (most recent call last):
  File "/srv/zulip-py3-venv/bin/zulip-run-bot", line 11, in <module>
    load_entry_point('zulip-bots==0.3.9', 'console_scripts', 'zulip-run-bot')()
  File "/srv/zulip-venv-cache/d84103380ddb988820877df4a2480a7ee4c2d737/zulip-py3-venv/lib/python3.5/site-packages/zulip_bots/run.py", line 124, in main
    lib_module = import_module_from_source(bot_path, bot_name)
  File "/srv/zulip-venv-cache/d84103380ddb988820877df4a2480a7ee4c2d737/zulip-py3-venv/lib/python3.5/site-packages/zulip_bots/run.py", line 37, in import_module_from_source
    spec.loader.exec_module(module)
  File "<frozen importlib._bootstrap_external>", line 661, in exec_module
  File "<frozen importlib._bootstrap_external>", line 766, in get_code
  File "<frozen importlib._bootstrap_external>", line 818, in get_data
FileNotFoundError: [Errno 2] No such file or directory: '/srv/zulip-venv-cache/d84103380ddb988820877df4a2480a7ee4c2d737/zulip-py3-venv/lib/python3.5/site-packages/zulip_bots/bots/ivche_helloworld_bot/ivche_helloworld_bot.py'



But then i fixed it like this:
    $ zulip-run-bot helloworld --config-file ~/zuliprc-my-bot

