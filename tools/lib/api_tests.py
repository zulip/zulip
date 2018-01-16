
if False:
    from zulip import Client

def add_subscriptions(client):
    # type: (Client) -> None

    request = [
        dict(
            name='new stream',
            description='New stream for testing',
        )
    ]
    result = client.add_subscriptions(request)
    assert result['result'] == 'success'

def create_user(client):
    # type: (Client) -> None

    request = dict(
        email='newbie@zulip.com',
        full_name='New User',
        short_name='Newbie',
        password='temp',
    )
    result = client.create_user(request)
    assert result['result'] == 'success'

def get_members(client):
    # type: (Client) -> None

    result = client.get_members()
    assert result['result'] == 'success'
    members = [m for m in result['members'] if m['email'] == 'newbie@zulip.com']
    assert len(members) == 1
    iago = members[0]

    assert not iago['is_admin']
    assert iago['full_name'] == 'New User'

def get_profile(client):
    # type: (Client) -> None

    result = client.get_profile()
    assert result['is_admin']
    assert result['email'] == 'iago@zulip.com'
    assert result['full_name'] == 'Iago'

def get_stream_id(client):
    # type: (Client) -> None

    stream_name = 'new stream'
    result = client.get_stream_id(stream_name)
    assert int(result['stream_id'])

def get_streams(client):
    # type: (Client) -> None

    result = client.get_streams()
    assert result['result'] == 'success'
    streams = [s for s in result['streams'] if s['name'] == 'new stream']
    assert streams[0]['description'] == 'New stream for testing'

def get_subscribers(client):
    # type: (Client) -> None

    result = client.get_subscribers(stream='new stream')
    assert result['subscribers'] == ['iago@zulip.com']

def get_user_agent(client):
    # type: (Client) -> None

    result = client.get_user_agent()
    assert result.startswith('ZulipPython/')

def list_subscriptions(client):
    # type: (Client) -> None

    result = client.list_subscriptions()
    assert result['result'] == 'success'
    streams = [s for s in result['subscriptions'] if s['name'] == 'new stream']
    assert streams[0]['description'] == 'New stream for testing'

def remove_subscriptions(client):
    # type: (Client) -> None

    result = client.remove_subscriptions(['new stream'])
    assert result['result'] == 'success'

    # test it was actually removed
    result = client.list_subscriptions()
    assert result['result'] == 'success'
    streams = [s for s in result['subscriptions'] if s['name'] == 'new stream']
    assert len(streams) == 0

def render_message(client):
    # type: (Client) -> None

    request = dict(content='**foo**')
    result = client.render_message(request)
    assert result['result'] == 'success'
    assert result['rendered'] == '<p><strong>foo</strong></p>'

def send_message(client):
    # type: (Client) -> int

    request = dict(
        type='stream',
        to='Denmark',
        subject='Copenhagen',
        content='hello',
    )
    result = client.send_message(request)
    assert result['result'] == 'success'
    message_id = result['id']

    # test it was actually sent
    url = 'messages/' + str(message_id)
    result = client.call_endpoint(
        url=url,
        method='GET'
    )
    assert result['result'] == 'success'
    assert result['raw_content'] == 'hello'

    return message_id

def update_message(client, message_id):
    # type: (Client, int) -> None

    assert int(message_id)
    request = dict(
        message_id=message_id,
        content='new content',
    )
    result = client.update_message(request)
    assert result['result'] == 'success'

    # test it was actually updated
    url = 'messages/' + str(message_id)
    result = client.call_endpoint(
        url=url,
        method='GET'
    )
    assert result['result'] == 'success'
    assert result['raw_content'] == 'new content'

# SETUP METHODS FOLLOW

def test_messages(client):
    # type: (Client) -> None

    render_message(client)
    message_id = send_message(client)
    update_message(client, message_id)

def test_users(client):
    # type: (Client) -> None

    create_user(client)
    get_members(client)
    get_profile(client)

def test_streams(client):
    # type: (Client) -> None

    add_subscriptions(client)
    list_subscriptions(client)
    get_stream_id(client)
    get_streams(client)
    get_subscribers(client)

def test_the_api(client):
    # type: (Client) -> None

    get_user_agent(client)
    test_users(client)
    test_streams(client)
    test_messages(client)

    # print(dir(client))
