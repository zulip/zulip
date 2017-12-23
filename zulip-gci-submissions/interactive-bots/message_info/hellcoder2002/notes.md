I ran into a bunch of errors.First one is running into
no directory error.While running the bot,I forgot to create
a folder named message_info.

Second one is about multiple instances of the same file.
I had to move the message_info.py file into the folder I created.
Instead,I just copied it into the new folder.I was editting in the
original one.I learnt to be careful

Third one is while running the test case.
I accidentally took out the

  ```def test_bot(self) -> None:```

which led to this error,

  ```
  File "c:\users\new\python-zulip-api\zulip_bots\zulip_bots\bots\message_info\te                                                                                          st_message_info.py", line 14, in TestMessageInfoBot
  self.check_expected_responses(expected_conversation, expected_method='send_m                                                                                          essage')
  NameError: name 'self' is not defined
  ```

It took me some time to identify it.

  