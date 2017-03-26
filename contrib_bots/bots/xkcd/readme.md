# xkcd bot

xkcd bot is a Zulip bot that can fetch a comic strip from xkcd. To use xkcd
bot you can simply call it with `@xkcd` followed by a command. Like this:

```
@xkcd <command>
```

xkcd bot has four commands:  

1. `help`  
This command is used to list all commands that can be used with this bot.
You can use this command by typing `@xkcd help` in a stream.  
![](assets/xkcd-help.png)

2. `latest`  
This command is used to fetch the latest comic strip from xkcd. You can use
this command by typing `@xkcd latest` in a stream.  
![](assets/xkcd-latest.png)

3. `random`  
This command is used to fetch a random comic strip from xkcd. You can use
this command by typing `@xkcd random` in a stream, xkcd bot will post a
random xkcd comic strip.  
![](assets/xkcd-random.png)

4. `<comic_id>`  
To fetch a comic strip based on id, you can directly use `@xkcd <comic_id>`,
for example if you want to fetch a comic strip with id 1234, you can type
`@xkcd 1234`, xkcd bot will post a comic strip with id 1234.  
![](assets/xkcd-specific-id.png)  

If you type a wrong command to xkcd bot, xkcd bot will post information
you'd get from `@xkcd help`.  
![](assets/xkcd-wrong-command.png)

And if you type a wrong id, xkcd bot will post a message that an xkcd comic
strip with that id is not available.  
![](assets/xkcd-wrong-id.png)
