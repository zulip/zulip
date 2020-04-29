# Get attachments

{generate_api_description(/attachments:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/attachments:get|example}

{tab|curl}

{generate_code_example(curl)|/attachments:get|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/attachments:get}

## Response

#### Return values

* `attachments`: An array of `attachment` objects with details of the attachment.
    * `id`: The ID of the attachment.
    * `name`: Name of the file.
    * `path_id`: A representation of the path of the file. If the path of a file is
       `{server_url}/user_uploads/a/b/abc/temp_file.py` then its path_id
       will be `a/b/abc/temp_file.py`.
    * `size`: Size of the file.
    * `create_time`: Time when the attachment was uploaded.
    * `messages`: Contains the details of the messages where the same uploaded attachment
       link has been used, for example, copy-pasted, used with quote and reply, etc.
* `upload_space_used`: Total upload space used by the requesting user in bytes.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/attachments:get|fixture(200)}
