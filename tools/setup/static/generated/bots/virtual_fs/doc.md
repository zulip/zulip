# Virtual fs bot

This bot allows users to store information in a virtual file system,
for a given stream or private chat.

## Usage

Run this bot as described in
[here](https://zulipchat.com/api/running-bots#running-a-bot).

Use this bot with any of the following commands:

`@fs mkdir` : create a directory
`@fs ls` : list a directory
`@fs cd` : change directory
`@fs pwd` : show current path
`@fs write` : write text
`@fs read` : read text
`@fs rm` : remove a file
`@fs rmdir` : remove a directory

where `fs` may be the name of the bot you registered in the zulip system.

### Usage examples

`@fs ls` - Initially shows nothing (with a warning)
`@fs pwd` - Show which directory we are in: we start in /
`@fs mkdir foo` - Make directory foo
`@fs ls` - Show that foo is now created
`@fs cd foo` - Change into foo (and do a pwd, automatically)
`@fs write test hello world` - Write "hello world" to the file 'test'
`@fs read test` - Check the text was written
`@fs ls` - Show that the new file exists
`@fs rm test` - Remove that file
`@fs cd /` - Change back to root directory
`@fs rmdir foo` - Remove foo

## Notes

* In a stream, the bot must be mentioned; in a private chat, the bot
  will assume every message is a command and so does not require this,
  though doing so will still work.

* Use commands like `@fs help write` for more details on a command.
