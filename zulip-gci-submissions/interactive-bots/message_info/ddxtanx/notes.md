During the development process there was one minor hitch I got into,

When I ran the tests for message_info initially, I kept getting a wierd
AttributeError (shown in FailTestWithError.jpg)and asked about it on the Zulip
chat for GCI students, and I got no resolving answer. It took me a while until
I looked back at the Zulip tutorial on how to write a bot, and specifically 
it's tests, until I realized a problem with the testing framwork import. I 
changed the StubBotTestCase to a BotTestCase (A change I showed in
ChangedTestImport.jpg) and it worked smoothly from there. Other than that, 
development was easy and smooth! 
