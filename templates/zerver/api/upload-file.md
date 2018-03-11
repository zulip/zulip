# Upload a file

Upload a single file and get the corresponding URI.

`POST {{ api_url}}/v1/user_uploads`

## Usage examples
<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="python">Python</li>
</ul>
<div class="blocks">

<div data-language="python" markdown="1">

{generate_code_example(python)|upload-file|example}

</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|arguments.json|upload-file.md}

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

{generate_code_example|upload-file|fixture}
