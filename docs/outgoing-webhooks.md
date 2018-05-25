# Outgoing Webhooks

Outgoing webhooks are a type of integration where the Zulip server sends HTTP POST requests to a third party URL.
To create an outgoing webhook, go to the `Add a new bot` tab in bot settings, and select the following options:
* **Bot type**: outgoing webhook
* **Full name, Username**: as desired, the username will be taken as name of outgoing webhook
* **Base URL**: desired URL to which data is to be posted
* **Interface**: generic for simple outgoing webhooks, else desired interface as per use


![Add new bot form](images/add_new_bot_form.png)


## Editing the details:
**Base URL** and **Interface** for an outgoing webhook can be edited by users, through the `Edit bot` form.
To open the `Edit bot` form, go to the `Active bots` tab, and for the outgoing webhook bot to be edited,
click on the pencil shaped icon below the bot's name.


![Edit bot form](images/edit_bot_form.png)


## Triggering
There are currently two methods to trigger an outgoing webhook:
1.  **@-mention the bot which is the owner of outgoing webhook**

    The bot you created through `Add new bot` ui is the owner of the outgoing webhook.
    In this case the outgoing webhook will send the response in the same stream where it was triggered.
    Note: make sure that the bot is subscribed to the stream where it is to be triggered.

2.  **Send a private message to the bot**

    This can be both 1:1 messages or a group message. The outgoing webhook would send the response in the
    private message space where it was triggered.


## Data posted
The data posted varies according to the interface used. To know about the data posted to URL, refer to
the section below.


## Interfaces
These are classes which customise the data to be posted to base URL of outgoing webhooks. These also provide
methods to prepare data to be posted, help parse the response from the URL and generate the response
to be sent to the user. For specialised purpose, user can create their own interface, else they can use
the following interfaces supported by zulip.

*   **Generic**

    It is useful for general purpose webhooks. It can also be used for zulip bot server. It posts the
    following data:

    ```
    data:       content of message in a more readable format
    token:      string of alphanumeric characters for identifying service on external URL servers
    message:    the message which triggered outgoing webhook
    ├── id
    ├── sender_email
    ├── sender_full_name
    ├── sender_short_name
    ├── sender_realm_str
    ├── sender_id
    ├── type
    ├── display_recipient
    ├── recipient_id
    ├── subject
    ├── timestamp
    ├── avatar_url
    ├── client
    ```
    The above data is posted as a json encoded dictionary.
    For a successful request, it receives either a json encoded dictionary or a string as response from the
    server. If the dictionary contains `response_not_required` set to `True`, no response message is sent to
    the user. Else if the dictionary contains `response_string` key, the corresponding value is returned as
    response message, else a default response message is sent.
    In the case of failed request, it returns the reason of failure, as returned by the server, or the
    exception message.


*   **Slack outgoing webhook**

    This interface translates the Zulip's outgoing webhook's request into Slack's outgoing webhook request.
    Hence the outgoing webhook bot would be able to post data to URLs which support Slack's outgoing webhooks.
    It posts the following data:
    ```
    token:          string of alphanumeric characters for identifying service on external URL servers
    team_id:        string id of realm
    team_domain:    domain of realm
    channel_id:     stream id
    channel_name:   stream name
    timestamp:      timestamp when message was sent
    user_id:        id of sender
    user_name:      full name of sender
    text:           content of message in a more readable format
    trigger_word:   trigger method
    service_id:     id of service

    ```
    The above data is posted as list of tuples. It isn't json encoded.
    For successful request, if data is returned, it returns that data, else it returns a blank response.
    For failed request, it returns the reason of failure, as returned by the server, or the exception message.


### Adding a new Interface
Adding interface requires following changes in the internal codebase:

1.  Define the interface in `zerver/lib/outgoing_webhook.py` file. It needs to extend the
    `OutgoingWebhookServiceInterface` class defined there. Override methods `process_event`,
    `process_success` and `process_failure`. They should return the minimum required data. For inspiration
    and documentation, refer to `OutgoingWebhookServiceInterface` class.
2.  Define a string constant corresponding to the interface in `zerver/models.py` and add an entry in the
    `Service` model inside `_interfaces` dictionary.
3.  Import the defined interface in `zerver/lib/outgoing_webhook.py` and add a corresponding entry in
    `AVAILABLE_OUTGOING_WEBHOOK_INTERFACES` dictionary, with key as the constant defined in previous step.
