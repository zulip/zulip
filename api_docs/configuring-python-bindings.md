# Configuring the Python bindings

Zulip provides a set of tools that allows interacting with its API more
easily, called the [Python bindings](https://pypi.python.org/pypi/zulip/).
One of the most notable use cases for these bindings are bots developed
using Zulip's [bot framework](/help/writing-bots).

In order to use them, you need to configure them with your identity
(account, API key, and Zulip server URL). There are a few ways to
achieve that:

- Using a [`zuliprc` file](/api/api-keys#download-a-zuliprc-file), referenced via
  the `--config-file` option or the `config_file` option to the
  `zulip.Client` constructor (recommended for bots).
- Using a [`zuliprc` file](/api/api-keys#download-a-zuliprc-file) in your home
  directory at `~/.zuliprc` (recommended for your own API key).
- Using the [environment
  variables](https://en.wikipedia.org/wiki/Environment_variable)
  documented [here](/api/api-keys#configuration-keys-and-environment-variables).
- Using the `--api-key`, `--email`, and `--site` variables as command
  line parameters.
- Using the `api_key`, `email`, and `site` parameters to the
  `zulip.Client` constructor.

## Related articles

* [Installation instructions](/api/installation-instructions)
* [API keys](/api/api-keys)
* [Running bots](/help/running-bots)
* [Deploying bots](/help/deploying-bots)
