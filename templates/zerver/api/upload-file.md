# Upload a file

Upload a single file and get the corresponding URI.

`POST {{ api_url }}/v1/user_uploads`

## Usage examples

{start_tabs}
{tab|python}
{generate_code_example(python)|/user_uploads:post|example}
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
