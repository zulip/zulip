# monkeytest.it bot

## Overview

This bot provides a quick way to check a site from a chat.
Using their monkeytestit's API  key, the user can check a website
for certain failures that user wants to see.

## Setting up API key

1. Get your monkeytest.it API key, located in your
   [dashboard](https://monkeytest.it/dashboard).

2. Create your own `monkeytestit.conf` file by copying the existing one in
   `bots/monkeytest/monkeytestit.conf`.

3. Inside the config file, you will see this:
   ```
   [monkeytestit]
   api_key = <api key here>
   ```

4. Replace `<api key here>` with your API key

5. Save the configuration file.

## Running the bot

Let `<path_to_config>` be the path to the config file, and let
`<path_to_zuliprc>` be the path to the zuliprc file.

You can run the bot by running:

`zulip-run-bot -b <path_to_config> monkeytestit --config-file
<path_to_zuliprc>`

## Usage

**Note**: You **must** not forget to put `http://` or `https://`
before a website. Otherwise, the check will fail.

### Simple check with default settings

To check a website with all enabled checkers, run:
`check https://website`

### Check with options

To check a website with certain enabled checkers, run:
`check https://website <checker_options>`

The checker options are supplied to: `on_load`, `on_click`, `page_weight`,
`seo`, `broken_links`, `asset_count` **in order**.

Example 1: Disable `on_load`, enable the rest  
command: `check https://website 0`

Example 2: Disable `asset_count`, enable the rest  
command: `check https//website 1 1 1 1 1 0`

Example 3: Disable `on_load` and `page_weight`, enable the rest  
command: `check https://website 0 1 0`

So for instance, if you wanted to disable `asset_count`, you have
to supply every params before it.
