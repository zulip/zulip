I was getting this error

======================================================================
ERROR: test_bot (zulip_bots.bots.message_info.test_message_info.TestHelpBot)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/zulipdev/python-zulip-api/zulip_bots/zulip_bots/bots/message_info/test_message_info.py", line 17, in test_bot
    self.check_expected_responses(expected_conversation, expected_method='send_message')
AttributeError: 'TestHelpBot' object has no attribute 'check_expected_responses'

----------------------------------------------------------------------
Ran 2 tests in 0.006s

FAILED (errors=1)

but then i imported BotTestCase and extended the TestHelpBot to it and i fixed the error.