# Setting Up VS Code for Debugging Zulip

## Overview

Set up VS Code to debug the django zulip sever. The following can only
setup VS Code to debug the *django application* and not the *JS*
(frontend) part of zulip. This is still a work in progress and any
suggestions to simplify or ease the workflow are encouraged.

I hope this helps the community of VS Code users working on zulip and
helps them significantly ! :D

## Steps

1. Download and install VS Code.
2. Download and install the
   [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
   extension for VS Code by Microsoft.  
3. Set up the vagrant dev environment from [here](./setup-advanced.md)
4. Make sure you run the dev server at least once. ( So that you know
   everything is working before making changes to the files )
5. Exposing *port* in Vagrant file

    Add the following line in `~/.zulip-vagrant-config`. If there is no
    `~/.zulip-vagrant-config` present, then create it.
    ```
    config.vm.network "forwarded_port", guest: 5678, host: 5678, host_ip: host_ip_addr
    ```

6. Edit `tools/settings.py`

    Add the following lines in `zproject/settings.py` after `if DEBUG:`
    ```python
    if DEBUG:                                   # Already present
        INTERNAL_IPS = ('127.0.0.1',)           # Already Present
        import ptvsd
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN"):
            try:
                ptvsd.enable_attach(redirect_output=True)
                print("VS Code Debugging Enabled.")
            except OSError:
                print("Debugging Setup Error, Exception: ")
                tracback.print_exc()
    ```

    The `redirect_output` gets the output from the server redirected to
    the debug console of VS Code (quite a handy thing!).

    Here you can have a bit of modifications like:
    - If you want the django server to wait for debugger *prior to
      running* just add
    ```python
    ...
    ptvsd.enable_attach()
    ptvsd.wait_for_debugger()
    ...
    ```
   - If you want to run the ptvsd server on some other port than default
     (default is *0.0.0.0* and *5678* ) then
    ```python
    ptvsd.enable_attach(YOUR_HOST_IP, YOUR_HOST_PORT)
    ```

7. Copy the `tools/setup/vscode-launch.json` file to your project's root
   `.vscode` directory (create one if not present) and rename it to
   `launch.json`. You can modify the internals to your liking, specifics of
   which can be found
   [here](https://code.visualstudio.com/docs/editor/debugging#_launch-configurations) and
   [here](https://github.com/microsoft/ptvsd).

8.  Launch `run-dev.py` via command line
9.  Attach the debugger from VS Code
10. Set up breakpoints and catch those nasty bugs!

## Note
- You need to attach the debugger everytime the sever reloads. No
  alternative to this right now.
- Haven't tested with manual installation of Zulip
- Not secure for running on production servers and / or for remote dev
  server (i.e. not on local servers).
