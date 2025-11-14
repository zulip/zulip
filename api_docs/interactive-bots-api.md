## Interactive bots API

This page documents functions available to the bot, and the structure of the
bot's config file.

With this API, you *can*

* intercept, view, and process messages sent by users on Zulip.
* send out new messages as replies to the processed messages.

With this API, you *cannot*

* modify an intercepted message (you have to send a new message).
* send messages on behalf of or impersonate other users.
* intercept direct messages (except for direct messages with the bot as an
explicit recipient).

## usage

*usage(self)*

is called to retrieve information about the bot.

### Arguments

* self - the instance the method is called on.

### Return values

* A string describing the bot's functionality

### Example implementation

```python
def usage(self):
    return '''
        This plugin will allow users to flag messages
        as being follow-up items.  Users should preface
        messages with "@followup".
        Before running this, make sure to create a channel
        called "followup" that your API user can send to.
        '''
```

## handle_message

*handle_message(self, message, bot_handler)*

handles user message.

### Arguments

* self - the instance the method is called on.

* message - a dictionary describing a Zulip message

* bot_handler - used to interact with the server, e.g., to send a message

### Return values

None.

### Example implementation

```python
  def handle_message(self, message, bot_handler):
     original_content = message['content']
     original_sender = message['sender_email']
     new_content = original_content.replace('@followup',
                                            'from %s:' % (original_sender,))

     bot_handler.send_message(dict(
         type='stream',
         to='followup',
         subject=message['sender_email'],
         content=new_content,
     ))
```
## bot_handler.send_message

*bot_handler.send_message(message)*

will send a message as the bot user.  Generally, this is less
convenient than *send_reply*, but it offers additional flexibility
about where the message is sent to.

### Arguments

* message - a dictionary describing the message to be sent by the bot

### Example implementation

```python
bot_handler.send_message(dict(
    type='stream', # can be 'stream' or 'private'
    to=channel_name, # either the channel name or user's email
    subject=subject, # message subject
    content=message, # content of the sent message
))
```

## bot_handler.send_reply

*bot_handler.send_reply(message, response)*

will reply to the triggering message to the same place the original
message was sent to, with the content of the reply being *response*.

### Arguments

* message - Dictionary containing information on message to respond to
 (provided by `handle_message`).
* response - Response message from the bot (string).

## bot_handler.update_message

*bot_handler.update_message(message)*

will edit the content of a previously sent message.

### Arguments

* message - dictionary defining what message to edit and the new content

### Example

From `zulip_bots/bots/incrementor/incrementor.py`:

```python
bot_handler.update_message(dict(
    message_id=self.message_id, # id of message to be updated
    content=str(self.number), # string with which to update message with
))
```

## bot_handler.storage

A common problem when writing an interactive bot is that you want to
be able to store a bit of persistent state for the bot (e.g., for an
RSVP bot, the RSVPs).  For a sufficiently complex bot, you want need
your own database, but for simpler bots, we offer a convenient way for
bot code to persistently store data.

The interface for doing this is `bot_handler.storage`.

The data is stored in the Zulip Server's database. Each bot user has
an independent storage quota available to it.

### Performance considerations

You can use `bot_handler.storage` in one of two ways:

- **Direct access**: You can use bot_handler.storage directly, which
will result in a round-trip to the server for each `get`, `put`, and
`contains` call.
- **Context manager**: Alternatively, you can use the `use_storage`
context manager to minimize the number of round-trips to the server. We
recommend writing bots with the context manager such that they
automatically fetch data at the start of `handle_message` and submit the
state to the server at the end.

### Context manager use_storage

`use_storage(storage: BotStorage, keys: List[str])`

The context manager fetches the data for the specified keys and stores
them in a `CachedStorage` object with a `bot_handler.storage.get` call for
each key, at the start. This object will not communicate with the server
until manually calling flush or getting some values that are not previously
fetched. After the context manager block is exited, it will automatically
flush any changes made to the `CachedStorage` object to the server.

#### Arguments
* storage - a BotStorage object, i.e., `bot_handler.storage`
* keys - a list of keys to fetch

#### Example

```python
with use_storage(bot_handler.storage, ["foo", "bar"]) as cache:
    print(cache.get("foo"))  # print the value of "foo"
    cache.put("foo", "new value")  # update the value of "foo"
# changes are automatically flushed to the server on exiting the block
```

### bot_handler.storage methods

When using the `use_storage` context manager, the `bot_handler.storage`
methods on the yielded object will only operate on a cached version of the
storage.

### bot_handler.storage.put

*bot_handler.storage.put(key, value)*

will store the value `value` in the entry `key`.

#### Arguments

* key - a UTF-8 string
* value - a UTF-8 string

#### Example

```python
bot_handler.storage.put("foo", "bar")  # set entry "foo" to "bar"
```

### bot_handler.storage.get

*bot_handler.storage.get(key)*

will retrieve the value for the entry `key`.

##### Arguments

* key - a UTF-8 string

#### Example

```python
bot_handler.storage.put("foo", "bar")
print(bot_handler.storage.get("foo"))  # print "bar"
```

### bot_handler.storage.contains

*bot_handler.storage.contains(key)*

will check if the entry `key` exists.

Note that this will only check the cache, so it would return `False` if no
previous call to `bot_handler.storage.get()` or `bot_handler.storage.put()`
was made for `key`, since the bot was restarted.

#### Arguments

* key - a UTF-8 string

#### Example

```python
bot_handler.storage.contains("foo")  # False
bot_handler.storage.put("foo", "bar")
bot_handler.storage.contains("foo")  # True
```

### bot_handler.storage marshaling

By default, `bot_handler.storage` accepts any object for keys and
values, as long as it is JSON-able. Internally, the object then gets
converted to an UTF-8 string. You can specify custom data marshaling
by setting the functions `bot_handler.storage.marshal` and
`bot_handler.storage.demarshal`. These functions parse your data on
every call to `put` and `get`, respectively.

### Flushing cached data to the server

When using the `use_storage` context manager, you can manually flush
changes made to the cache to the server, using the below methods.

### cache.flush

`cache.flush()`

will flush all changes to the cache to the server.

#### Example
```python
with use_storage(bot_handler.storage, ["foo", "bar"]) as cache:
    cache.put("foo", "foo_value")  # update the value of "foo"
    cache.put("bar", "bar_value")  # update the value of "bar"
    cache.flush()  # manually flush both the changes to the server
```

### cache.flush_one

`cache.flush_one(key)`

will flush the changes for the specified key to the server.

#### Arguments

- key - a UTF-8 string

#### Example
```python
with use_storage(bot_handler.storage, ["foo", "bar"]) as cache:
    cache.put("foo", "baz")  # update the value of "foo"
    cache.put("bar", "bar_value")  # update the value of "bar"
    cache.flush_one("foo")  # flush the changes to "foo" to the server
```

## Configuration file

```
 [api]
 key=<api-key>
 email=<email>
 site=<dev-url>
```

* key - the API key you created for the bot; this is how Zulip knows
  the request is from an authorized user.

* email - the email address of the bot, e.g., `some-bot@zulip.com`

* site - your development environment URL; if you are working on a
  development environment hosted on your computer, use
  `localhost:9991`

## Related articles

* [Writing bots](/api/writing-bots)
* [Writing tests for bots](/api/writing-tests-for-interactive-bots)
