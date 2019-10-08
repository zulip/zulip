# Run your favorite chatbot in Zulip!

0. [Install errbot](http://errbot.io/en/latest/user_guide/setup.html)
   and follow to instructions to setup a `config.py`.

0. Check our our [Errbot integration package for Zulip](https://github.com/zulip/errbot-backend-zulip)
   Clone this repository somewhere convenient.

0. Install the requirements listed in `errbot-backend-zulip/requirements.txt`.

0. Next, on your {{ settings_html|safe }}, [create a bot](/help/add-a-bot-or-integration) for
   {{ integration_display_name }}. Make sure that you select **Generic bot** as the **Bot type**.

0. Download your Zulip bot's `zuliprc` config file. You will need its content for the next step.

0. Edit your ErrBot's `config.py`. Use the following template for a minimal configuration:

        import logging

        BACKEND = 'Zulip'

        BOT_EXTRA_BACKEND_DIR = r'<path/to/errbot-backend-zulip>'
        BOT_DATA_DIR = r'<path/to/your/errbot/data/directory>'
        BOT_EXTRA_PLUGIN_DIR = r'<path/to/your/errbot/plugin/directory>'

        BOT_LOG_FILE = r'<path/to/your/errbot/logfile.log>'
        BOT_LOG_LEVEL = logging.INFO

        BOT_IDENTITY = {  # Fill this with the corresponding values in your bot's `.zuliprc`
          'email': '<err-bot@your.zulip.server>',
          'key': '<abcdefghijklmnopqrstuvwxyz123456>',
          'site': '<http://your.zulip.server>'
        }
        BOT_ADMINS = ('<your@email.address',)
        CHATROOM_PRESENCE = ()
        BOT_PREFIX = '<@**err-bot@your.zulip.server**>'  # Needed for errbot to respond to @-mentions

    Sections you need to edit are marked with `<>`.

7. [Start ErrBot](http://errbot.io/en/latest/user_guide/setup.html#starting-the-daemon).

{!congrats.md!}

![](/static/images/integrations/errbot/000.png)

Tips
----

* Rooms in ErrBot are streams in Zulip.
