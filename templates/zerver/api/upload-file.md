# Upload a file

{generate_api_description(/user_uploads:post)}

## Usage examples

{start_tabs}

{tab|python}

{generate_code_example(python)|/user_uploads:post|example}

{tab|curl}

{generate_code_example(curl)|/user_uploads:post|example}

{end_tabs}

## Parameters

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

{generate_return_values_table|zulip.yaml|/user_uploads:post}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/user_uploads:post|fixture(200)}
