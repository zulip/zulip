# Get user groups

Fetches all of the user groups in the organization.

`GET {{ api_url }}/v1/user_groups`

## Usage examples

<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="python">Python</li>
<li data-language="curl">curl</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl {{ api_url }}/v1/user_groups \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|/user_groups:get|example}

</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/user_groups:get}

## Response

#### Return values

* `user_groups`: A list of dictionaries, where each dictionary contains information
  about a user group.
    * `description`: The human-readable description of the user group.
    * `id`: The user group's integer id.
    * `members`: The integer User IDs of the user group members.
    * `name`: User group name.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/user_groups:get|fixture(200)}
