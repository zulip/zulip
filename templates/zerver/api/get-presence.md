# Get user presence

Get the presence status for a specific user.

This endpoint is most useful for embedding data about a user's
presence status in other sites (E.g. an employee directory).  Full
Zulip clients like mobile/desktop apps will want to use the main
presence endpoint, which returns data for all active users in the
organization, instead.

`GET {{ api_url }}/v1/users/<email>/presence`

See
[Zulip's developer documentation](https://zulip.readthedocs.io/en/latest/subsystems/presence.html)
for details on the data model for presence in Zulip.

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/{email}/presence:get|example}

{tab|curl}

```
curl {{ api_url }}/v1/users/<email>/presence \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/users/{email}/presence:get}

## Response

#### Return values

* `presence`: An object containing the presence details for every type
  of client the user has ever logged into.
    * `<client_name>` or `aggregated`: the keys for these objects are
      the names of the different clients where this user is logged in,
      like `website`, `ZulipDesktop`, `ZulipTerminal`, or
      `ZulipMobile`. There is also an `aggregated` key, which matches
      the contents of the object that has been updated most
      recently. For most applications, you'll just want to look at the
      `aggregated` key.
        * `timestamp`: when this update was received; if the timestamp
          is more than a few minutes in the past, the user is offline.
        * `status`: either `active` or `idle`: whether the user had
          recently interacted with Zulip at the time in the timestamp
          (this distinguishes orange vs. green dots in the Zulip web
          UI; orange/idle means we don't know whether the user is
          actually at their computer or just left the Zulip app open
          on their desktop).
        * `pushable`: whether the client accepts push notifications or not.
        * `client`: the name of the client this presence information refers to.
          Matches the object's key if this isn't the `aggregated` object.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/{email}/presence:get|fixture(200)}
