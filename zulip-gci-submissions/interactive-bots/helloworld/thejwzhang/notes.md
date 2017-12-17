# Notes

While completing this activity, I ran into a few issues, especially in regards to which commands to run and in what order.

When following the guide at https://zulipchat.com/api/running-bots#running-a-bot, I was initially unaware that I needed to be running my Zulip development server while performing these commands. 

Additionally, in step for with the command `zulip-run-bot <bot-name> --config-file ~/zuliprc-my-bot`, `<bot-name>` should not be the bot name you created, rather it should be helloworld. The guide on GitHub (https://github.com/zulip/zulip-gci/blob/master/tasks/2017/interactive-bots.md) describes this, and the information in each guide should be displayed in both. Also, the ~/zuliprc-my-bot is the directory as well as the file downloaded from the server. I placed mine in ~/Documents, and initially `~/Documents` was the only thing I had in place of `~/zuliprc-my-bot`, but from the chat I learned it should be `~/Documents/zuliprc` where zuliprc was the name of the file downloaded from the server.

I received permission denied as well as "No such file or directory" errors due to those two mistakes in the `zulip-run-bot` command.
