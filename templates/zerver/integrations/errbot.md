# Zulip Errbot integration

Run your favorite chatbot in Zulip!

{start_tabs}

1. [Install errbot][install-errbot], and follow the instructions to set up a
   `config.py`.

1. Clone the [Errbot integration package for Zulip][errbot-package]
   repository somewhere convenient, and install the requirements listed in
   `errbot-backend-zulip/requirements.txt`.

1. {!create-a-generic-bot.md!}

1. Edit your ErrBot's `config.py`. Use the following template for a minimal
   configuration:

        import logging

        BACKEND = 'Zulip'

        BOT_EXTRA_BACKEND_DIR = r'<path/to/errbot-backend-zulip>'
        BOT_DATA_DIR = r'<path/to/your/errbot/data/directory>'
        BOT_EXTRA_PLUGIN_DIR = r'<path/to/your/errbot/plugin/directory>'

        BOT_LOG_FILE = r'<path/to/your/errbot/logfile.log>'
        BOT_LOG_LEVEL = logging.INFO

        BOT_IDENTITY = {
          'email': '<your-bot@email.address>',
          'key': '<api-key-of-your-bot>',
          'site': '<your-zulip-organization-url>'
        }
        BOT_ADMINS = ('<your@email.address>',)
        CHATROOM_PRESENCE = ()
        BOT_PREFIX = '@**<your-bot-name>**'

    Sections you need to edit are marked with `<>`. Replace the `<...>`
    placeholders with your own values, removing the `<` and `>` brackets.

    Use the details of the Zulip bot created above for the `BOT_IDENTITY`
    and `BOT_PREFIX` sections.

1. [Start ErrBot][start-errbot].

!!! tip ""

    ErrBot uses the term "Rooms" for Zulip channels.

{end_tabs}

{!congrats.md!}

![Errbot message](/static/images/integrations/errbot/000.png)

### Related documentation

- [Errbot Documentation](https://errbot.readthedocs.io/en/latest/)
- [Errbot integration package for Zulip][errbot-package]
- [Python bindings Configuration][config-python-bindings]

[install-errbot]: https://errbot.readthedocs.io/en/latest/user_guide/setup.html
[errbot-package]: https://github.com/zulip/errbot-backend-zulip
[start-errbot]: https://errbot.readthedocs.io/en/latest/user_guide/setup.html#starting-the-daemon
[config-python-bindings]: https://zulip.com/api/configuring-python-bindings
