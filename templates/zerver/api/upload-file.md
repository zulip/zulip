# Upload a file

Upload a single file and get the corresponding URI.

`POST {{ api_url }}/v1/user_uploads`

Initially, only you will be able to access the link.  To share the
uploaded file, you'll need to [send a message][send-message]
containing the resulting link.  Users who can already access the link
can reshare it with other users by sending additional Zulip messages
containing the link.

[uploaded-files]: /help/manage-your-uploaded-files
[send-message]: /api/send-message

## Usage examples

{start_tabs}

{tab|python}

{generate_code_example(python)|/user_uploads:post|example}

{tab|curl}

{generate_code_example(curl)|/user_uploads:post|example}

{end_tabs}

## Arguments

As described above, the file to upload must be provided in the
request's body.

## Maximum file size

The maximum file size for uploads can be configured by the
administrator of the Zulip server by setting `MAX_FILE_UPLOAD_SIZE`
in the [server's settings][1]. `MAX_FILE_UPLOAD_SIZE` defaults
to 25MB.

[1]: https://zulip.readthedocs.io/en/latest/subsystems/settings.html#server-settings

## Response

#### Return values

* `uri`: The URI of the uploaded file.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/user_uploads:post|fixture(200)}
