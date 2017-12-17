There were a few issues, mainly the `zulip-run-bot helloworld --config-file ~/zuliprc-hello-world` command ran with the error
```
Traceback (most recent call last):
  File "/srv/zulip-py3-venv/bin/zulip-run-bot", line 11, in <module>
    load_entry_point('zulip-bots==0.3.8', 'console_scripts', 'zulip-run-bot')()
  File "/srv/zulip-venv-cache/e6ede0343bbe3ec1b5ff20d6263c9baded9bfc02/zulip-py3-venv/lib/python3.5/site-packages/zulip_bots/run.py", line 112, in main
    bot_name=bot_name
  File "/srv/zulip-venv-cache/e6ede0343bbe3ec1b5ff20d6263c9baded9bfc02/zulip-py3-venv/lib/python3.5/site-packages/zulip_bots/lib.py", line 230, in run_message_handler_for_bot
    restricted_client = ExternalBotHandler(client, bot_dir, bot_details)
  File "/srv/zulip-venv-cache/e6ede0343bbe3ec1b5ff20d6263c9baded9bfc02/zulip-py3-venv/lib/python3.5/site-packages/zulip_bots/lib.py", line 111, in __init__
    self._storage = StateHandler(client)
  File "/srv/zulip-venv-cache/e6ede0343bbe3ec1b5ff20d6263c9baded9bfc02/zulip-py3-venv/lib/python3.5/site-packages/zulip_bots/lib.py", line 68, in __init__
    raise StateHandlerError("Error initializing state: {}".format(str(response)))
zulip_bots.lib.StateHandlerError: Error initializing state: {'msg': 'Unexpected error from the server', 'result': 'http-error', 'status_code': 404}
```
This needed to be fixed, and once it was, I had also accidentally not downloaded the development version of the `zulip_bots` package. However, eventually everything was fixed, and the bot ran perfectly, by uninstalling the `zulip_bots` package, then running the appropriate setup steps from the `python-zulip-api` repository.