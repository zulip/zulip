# Upload a custom emoji

This endpoint is used to upload a custom emoji for use in the user's
organization.  Access to this endpoint depends on the
[organization's configuration](https://zulipchat.com/help/only-allow-admins-to-add-emoji).

 `POST {{ api_url }}/v1/realm/emoji/<emoji_name>`

## Usage examples

{start_tabs}

{tab|python}

{generate_code_example(python)|/realm/emoji/<emoji_name>:post|example}

{tab|curl}

```
curl {{ api_url }}/v1/realm/emoji/<emoji_name> \
    -F "data=@/path/to/img.png" \
    -u USER_EMAIL:API_KEY
```

{end_tabs}


## Arguments

As described above, the image file to upload must be provided in the
request's body.

## Emoji name

The emoji name can only contain letters, numbers, dashes, and spaces.
Upper and lower case letters are treated the same, and underscores (_)
are treated the same as spaces (consistent with how the Zulip UI
handles emoji).

## Maximum file size

The maximum file size for uploads can be configured by the
administrator of the Zulip server by setting `MAX_EMOJI_FILE_SIZE`
in the [server's settings][1]. `MAX_EMOJI_FILE_SIZE` defaults
to 5MB.

[1]: https://zulip.readthedocs.io/en/latest/subsystems/settings.html#server-settings

## Response
#### Example response

A typical successful JSON response may look like:

{generate_code_example|/realm/emoji/<emoji_name>:post|fixture(200)}
