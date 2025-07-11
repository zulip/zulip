# Google Translate bot

The Google Translate bot uses Google Translate to translate
any text sent to it.

## Setup

This bot requires a google cloud API key. Create one
[here](https://support.google.com/cloud/answer/6158862?hl=en)

You should add this key to `googletranslate.conf`.

To run this bot, use:
`zulip-run-bots googletranslate -c <zuliprc file>
--bot-config-file <path to googletranslate.conf>`

## Usage

To use this bot, @-mention it like this:

`@-mention "<text>" <target language> <source language(Optional)>`

`text` must be in quotation marks, and `source language`
is optional.

If `source language` is not given, it will automatically detect your language.
