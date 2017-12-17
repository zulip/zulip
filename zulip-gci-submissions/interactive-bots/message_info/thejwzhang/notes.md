# Notes

I ran into a couple of issues in this task, and I have created a PR on the 
instructions page to clarify some of the issues.

First, when trying to run the bot, I initially only typed in the bot name 
to the command as follows: `zulip-run-bot message_info --config-file ~/Documents/zuliprc`. 
After consulting mentors, I found out instead of  message_info it should be the
full path to the message_info bot.

Second, when editing the commands, I did not realize that the commands in the
instructions were meant to be added into the functions, not replaced. I have 
included this into my PR. Initially the bot was receiving the messages I sent,
but I deleted the `bot_handler.send_reply(message, "message text")` line so it
did not send any replies.

Third, when I tried to run the tests, it gave me a ModuleNotFoundError. This 
was resolved when reactivated the virtualenv, which was disabled when I 
restarted Git Bash. See the guide for installing the Zulip bots package.