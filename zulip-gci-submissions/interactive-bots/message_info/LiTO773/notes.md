The task went fine and it was actually pretty fun to see how many words some 
texts have (like *Never Gonna Give You Up*'s chorus 😀). However I did ran into 
some issues, which I'll point out here:

## Python 2 or Python 3?
I didn't know what version of Python to run. I used Python 3 since that is the 
version the provided droplet is using, but I think that it should be a bit more 
clear what version to use.

## Bot Testing
This error was popping up everytime I tried to test my bot 
(`tools/test-bots message_info`):

```python
test_bot (zulip_bots.bots.message_info.test_message_info.TestHelpBot) ... ERROR
test_bot_usage (zulip_bots.bots.message_info.test_message_info.TestHelpBot) ... ok

======================================================================
ERROR: test_bot (zulip_bots.bots.message_info.test_message_info.TestHelpBot)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/luis/Desktop/Main/Zulip/task-b/python-zulip-api/zulip_bots/zulip_bots/bots/message_info/test_message_info.py", line 16, in test_bot
    self.check_expected_responses(expected_conversation, expected_method='send_message')
AttributeError: 'TestHelpBot' object has no attribute 'check_expected_responses'

----------------------------------------------------------------------
Ran 2 tests in 0.001s

FAILED (errors=1)
```

I later found out that this was caused by the fact that the boilerplate 
helloworld bot uses `StubBotTestCase` for testing, instead of `BotTestCase`, 
which doesn't have the attribute `check_expected_responses`.

However this wasn't a hard issue to fix, in fact the Zulip's documentation was 
super useful ([link to the documentation](
https://www.zulipchat.com/api/writing-bots#a-simple-example)).