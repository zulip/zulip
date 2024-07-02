# Dropbox Bot

This bot links your [dropbox](https://www.dropbox.com) account to [zulip](https://chat.zulip.org).

## Usage

 - Create a dropbox app from [here](https://www.dropbox.com/developers/apps).
 - Click the `generate` button under the **Generate access token** section.
 - Copy the Access Token and paste it in a file named `dropbox_share.conf` as shown:
    ```
    [dropbox_share]
    ACCESS_TOKEN=<your_access_token>
    ```
 - Follow the instructions as described in [here](https://zulipchat.com/api/running-bots#running-a-bot).
 - Run the bot: `zulip-run-bot dropbox_share -b <Path/to/dropbox_share.conf> -c <Path/to/zuliprc>`

Use this bot with any of the following commands:

- `@dropbox mkdir` : Create a folder
- `@dropbox ls` : List contents of a folder
- `@dropbox write` : Save text to a file
- `@dropbox rm` : Remove a file/folder
- `@dropbox help` : See help text
- `@dropbox read`: Read contents of a file
- `@dropbox share`: Get a shareable link for a file/folder
- `@dropbox search`: Search for matching file/folder names

where `dropbox` may be the name of the bot you registered in the zulip system.

### Usage examples

- `dropbox ls -` Shows files/folders in the root folder.
- `dropbox mkdir foo` - Make folder named foo.
- `dropbox ls foo/boo` - Shows the files/folders in foo/boo folder.
- `dropbox write test hello world` - Write "hello world" to the file 'test'.
- `dropbox rm test` - Remove the file/folder test.
- `dropbox read foo` - Read the contents of file/folder foo.
- `dropbox share foo` - Get shareable link for the file/folder foo.
- `dropbox search boo` - Search for boo in root folder and get at max 20 results.
- `dropbox search boo --mr 10` - Search for boo and get at max 10 results.
- `dropbox search boo --fd foo` - Search for boo in folder foo.
