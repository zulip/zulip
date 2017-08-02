# Poll bot

The poll bot maintains up to one poll per user, per topic, in streams only.
It currently keeps a running count of the votes, as they are made, with one
message in the stream being updated to show the current status.

## Usage

The bot can be messaged:

* privately; the stream and topic must be mentioned explicitly in some commands
(as in `[<stream> <topic>]` below), and a '+' must be used in place of any
spaces in the stream or topic names.

* in a stream/topic; the poll location is then implied to be in that stream and
topic. The bot must be mentioned in this case, eg. each of the commands must
be preceded with `@botname`, where botname is the bot user running this code.  

The bot has the following commands, the success or failure of each being
reported privately to the user attempting them:

* **commands**:
This command simply provides a concise listing of the available bot commands,
which should give a list of the following.

* **about**:
This command explains what the bot is for.

* **help**:
This command provides a more detailed help listing than just the commands.

* **new**:
This command adds a new poll in the specified stream/topic, for the user.
The format of this command is:
```
new [<stream> <topic>]
<poll title>
<option 1>
<option 2>
  ...
```
This produces a message in the stream/topic with the new poll details.
It will fail if the user already has a poll in the stream/topic, in which
case a different stream/topic can be used, or the current poll ended with
the **end** command. A poll must have a title/question, and at least 2 options.

* **vote**:
This command allows any user to vote on a currently running poll, started
with **new**.
The format of this command is:
```
vote [<stream> <topic>] <poll id> <option number>
```
where `<poll id>` is the id of an active poll, as given in the main poll message
output after the **new** command has been made.
This currently attempts to update (edit) the poll message to indicate the vote.

* **end**:
This command allows a user to end a currently running poll.
The format of this command is:
```
end [<stream> <topic>]  
```
The bot will attempt to update (edit) the poll message to indicate the poll has
closed.
This will fail if there is no active poll running in the specified topic for
the user.

### Example usage

#### In a particular stream & topic

```
@pollbot commands
```

```
@pollbot about
```

```
@pollbot help
```

```
@pollbot new
How do you like the new poll bot service?
Beyond measure!
It's ok.
It's terrible.
```

```
@pollbot vote 2406 1
```

```
@pollbot end
```

#### From a private message with the pollbot

```
commands
```

```
about
```

```
help
```

```
new bot+testing testing+here
How do you like the new poll bot service?
Beyond measure!
It's ok.
It's terrible.
```

```
vote bot+testing testing+here 2406 1
```

```
@pollbot end
```


## Outstanding Bugs, Limitations & Issues

### Larger issues

* Polls can be explicitly ended, but also end if the bot is terminated or (if
implemented) if the message cannot be updated. This could occur if the server
is configured to not allow message editing, or only for a finite time (eg. 1
hour), which the bot currently has no way of querying. The current state for each
poll is stored within the bot, but also within the poll messages, which could
allow for restarting/continuing polls if they could be queried.
* The help text could be improved?

### Potential areas to develop

* Support changing of votes? (optionally)
* Show votes only at the end of a vote? (optionally)
* Support different vote schemes (eg. voting preferences for each option)
* Support external vote engines?

### Design decisions

* Polls are limited to one per user per topic per stream (thought to be sufficient).
* Polls are only in streams (this is an intentional initial design).
