# Notes

# 1
I ran into an error while setting up the development environment.
I cloned the `zulip/python-zulip-api` repo  and ran `./tools/provision`
It was running into this error :
```
./tools/provision
Virtualenv already exists.
Traceback (most recent call last):
  File "./tools/provision", line 108, in <module>
    main()
  File "./tools/provision", line 88, in main
    install_dependencies('requirements.txt')
  File "./tools/provision", line 82, in install_dependencies
    subprocess.call([pip_path, 'install', 'pip>=9.0'])
  File "/usr/lib/python2.7/subprocess.py", line 523, in call
    return Popen(*popenargs, **kwargs).wait()
  File "/usr/lib/python2.7/subprocess.py", line 711, in __init__
    errread, errwrite)
  File "/usr/lib/python2.7/subprocess.py", line 1343, in _execute_child
    raise child_exception
OSError: [Errno 2] No such file or directory
```
I tried to solve the error myself , did a bit of searching but with no luck.
I asked at [Zulip chat room](https://chat.zulip.org/#narrow/stream/bots/topic/setup.20dev.20environment) and solved this by removing the directory and running provision again.
# 2

I was runnig the server and tried to run the bot but ran into this error :
```
olume/zulip/bots$ zulip-run-bot helloworld --config-file zuliprc
Traceback (most recent call last):
  File "/media/siva_/NewVolume/zulip/bots/zulip-api-py3-venv/bin/zulip-run-bot", line 11, in <module>
    load_entry_point('zulip-bots', 'console_scripts', 'zulip-run-bot')()
  File "/media/siva_/NewVolume/zulip/bots/zulip_bots/zulip_bots/run.py", line 141, in main
    bot_name=bot_name
  File "/media/siva_/NewVolume/zulip/bots/zulip_bots/zulip_bots/lib.py", line 268, in run_message_handler_for_bot
    restricted_client = ExternalBotHandler(client, bot_dir, bot_details, bot_config_file)
  File "/media/siva_/NewVolume/zulip/bots/zulip_bots/zulip_bots/lib.py", line 115, in __init__
    self._storage = StateHandler(client)
  File "/media/siva_/NewVolume/zulip/bots/zulip_bots/zulip_bots/lib.py", line 71, in __init__
    raise StateHandlerError("Error initializing state: {}".format(str(response)))
zulip_bots.lib.StateHandlerError: Error initializing state: {'status_code': 404, 'msg': 'Unexpected error from the server', 'result': 'http-error'}
```

I solved this by running the provision again on dev-server and the restarting the dev-server

