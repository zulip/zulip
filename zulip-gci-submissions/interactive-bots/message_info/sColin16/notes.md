Problems Faced:
===============

1. **Running the message_info bot** - Simply running
```zulip-run-bot message_info ... ```
was insufficient.
Instead, I had to run the command
```zulip-run-bot ~/.../message_info.py ...```
noting the path to the bot's file.

2. **Running the Unit Test** - The first time the unit test was run,
it failed to find certain files. I had to run ```/tools/provision```
to set up those files .

3. **Unknown Error** - After attempting to run the bots again,
I received a cryptic error. I had to pull changes from the
```python-zulip-api``` repo to make the bots work again.


Screenshot Notes
================
* **bot-terminal..png** - Demonstrates the message_info bot being run in the terminal.

* **bot-behavior.png** - Demonstrates the message_info bot behaving as expected.

* **bot-unittest.png** - Demonstrates the message_info unit tests passing
