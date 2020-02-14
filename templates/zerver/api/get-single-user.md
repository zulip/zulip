# Get a user

Fetch data about a single user in the organization.

`GET {{ api_url }}/v1/users/{user_id}`

To fetch users in bulk, see [Get all users](/api/get-all-users).

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/{user_id}:get|example}

{tab|curl}

{generate_code_example(curl, include=[""])|/users/{user_id}:get|example}

You may pass the `client_gravatar` or `include_custom_profile_fields` query parameter as follows:

{generate_code_example(curl)|/users/{user_id}:get|example}

{end_tabs}

## Arguments

**Note**: The following arguments are all URL query parameters.

{generate_api_arguments_table|zulip.yaml|/users/{user_id}:get}

## Response

#### Return values

* `members`: A list with a single dictionary that contains information
  about a particular user or bot.
    * `email`: The email address of the user or bot.
    * `is_bot`: A boolean specifying whether the user is a bot or not.
    * `avatar_url`: URL to the user's gravatar. `None` if the `client_gravatar`
      query paramater was set to `True`.
    * `full_name`: Full name of the user or bot.
    * `is_admin`: A boolean specifying whether the user is an admin or not.
    * `bot_type`: `None` if the user isn't a bot. `1` for a `Generic` bot.
      `2` for an `Incoming webhook` bot. `3` for an `Outgoing webhook` bot.
      `4` for an `Embedded` bot.
    * `user_id`: The ID of the user.
    * `bot_owner`: If the user is a bot (i.e. `is_bot` is `True`), `bot_owner`
      is the email address of the user who created the bot.
    * `is_active`: A boolean specifying whether the user is active or not.
    * `is_guest`: A boolean specifying whether the user is a guest user or not.
    * `timezone`: The time zone of the user.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/{user_id}:get|fixture(200)}
