# Notes 

When doing this task, I didn't run into any major problems. I was surprised that I didn't encounter any errors that slowed me down. 

I did, however run into an error when first running the bot. The config file was in the current directory so I thought I needed to do this: 

$ zulip-run-bot hellworld --config-file ./

however, I realized my mistake and corrected it: 

$ zulip-run-bot hellworld --config-file zuliprc