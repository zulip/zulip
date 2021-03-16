# Wit.ai Bot

Wit.ai Bot uses [wit.ai](https://wit.ai/) to parse natural language.

## Usage

 1. Go to https://wit.ai/ and sign up.

 2. Create your Wit.ai app, or follow
    [this quickstart guide](https://wit.ai/docs/quickstart).

 3. Create a `.conf` file containing a `token` field for your Wit.ai token,
    and a `help_message` field for a message to display to confused users,
    e.g.,

    ```
    [witai]
    token = QWERTYUIOP1234
    help_message = Ask me about my favorite food!
    ```

 4. Create a new file named `witai_handler.py`, and inside of it, create a
    function called `handle` with one parameter `response`. Inside of `handle`,
    write code for whatever you want to do with the Wit.ai response. It should
    return a `string` to respond to the user with. For example,

    ```python
    def handle(response):
        if response['entities']['intent'][0]['value'] == 'favorite_food':
            return 'pizza'
        if response['entities']['intent'][0]['value'] == 'favorite_drink':
            return 'coffee'
    ```

 5. Add `witai_handler.py`'s location as `handler_location` in your
    configuration file, e.g.,

    ```
    [witai]
    token = QWERTYUIOP1234
    handler_location = /Users/you/witai_handler_directory/witai_handler.py
    ```

 6. Call

    ```bash
    zulip-run-bot witai \
        --config-file <your zuliprc> \
        --bot-config-file <the config file>
    ```

    to start the bot.
