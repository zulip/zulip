
const events = require('./lib/events.js');
const event_fixtures = events.fixtures;

const noop = function () {};

zrequire('server_events_dispatch');

const dispatch = server_events_dispatch.dispatch_normal_event;

function test(label, f) {
    run_test(label, () => {
        global.with_overrides(f);
    });
}

test('add', (override) => {
    const event = event_fixtures.subscription__add;
    global.with_stub(function (subscription_stub) {
        global.with_stub(function (stream_email_stub) {
            override('stream_data.get_sub_by_id', function (stream_id) {
                return {stream_id: stream_id};
            });
            override('stream_events.mark_subscribed', subscription_stub.f);
            override('stream_data.update_stream_email_address', stream_email_stub.f);
            dispatch(event);
            let args = subscription_stub.get_args('sub', 'subscribers');
            assert.deepEqual(args.sub.stream_id, event.subscriptions[0].stream_id);
            assert.deepEqual(args.subscribers, event.subscriptions[0].subscribers);
            args = stream_email_stub.get_args('sub', 'email_address');
            assert.deepEqual(args.email_address, event.subscriptions[0].email_address);
            assert.deepEqual(args.sub.stream_id, event.subscriptions[0].stream_id);
        });
    });
});

test('peer add/remove', (override) => {
    const stream_edit_stub = global.make_stub();
    override('stream_edit.rerender', stream_edit_stub.f);

    const compose_fade_stub = global.make_stub();
    override('compose_fade.update_faded_users', compose_fade_stub.f);

    let event = event_fixtures.subscription__peer_add;
    global.with_stub(function (stub) {
        override('stream_data.add_subscriber', stub.f);
        dispatch(event);
        const args = stub.get_args('stream_name', 'user_id');
        assert.deepEqual(args.stream_name, 'devel');
        assert.deepEqual(args.user_id, 555);
    });
    assert.equal(compose_fade_stub.num_calls, 1);
    assert.equal(stream_edit_stub.num_calls, 1);

    event = event_fixtures.subscription__peer_remove;
    global.with_stub(function (stub) {
        override('stream_data.remove_subscriber', stub.f);
        dispatch(event);
        const args = stub.get_args('stream_name', 'user_id');
        assert.deepEqual(args.stream_name, 'prod help');
        assert.deepEqual(args.user_id, 555);
    });
    assert.equal(compose_fade_stub.num_calls, 2);
    assert.equal(stream_edit_stub.num_calls, 2);
});

test('remove', (override) => {
    const event = event_fixtures.subscription__remove;
    let stream_id_looked_up;
    const sub_stub = 'stub';
    override('stream_data.get_sub_by_id', function (stream_id) {
        stream_id_looked_up = stream_id;
        return sub_stub;
    });
    global.with_stub(function (stub) {
        override('stream_events.mark_unsubscribed', stub.f);
        dispatch(event);
        const args = stub.get_args('sub');
        assert.deepEqual(stream_id_looked_up, event.subscriptions[0].stream_id);
        assert.deepEqual(args.sub, sub_stub);
    });
});

test('update', (override) => {
    const event = event_fixtures.subscription__update;
    global.with_stub(function (stub) {
        override('stream_events.update_property', stub.f);
        dispatch(event);
        const args = stub.get_args('stream_id', 'property', 'value');
        assert.deepEqual(args.stream_id, event.stream_id);
        assert.deepEqual(args.property, event.property);
        assert.deepEqual(args.value, event.value);
    });
});

test('add error handling', (override) => {
    // test blueslip errors/warns
    const event = event_fixtures.subscription__add;
    global.with_stub(function (stub) {
        override('stream_data.get_sub_by_id', noop);
        override('blueslip.error', stub.f);
        dispatch(event);
        assert.deepEqual(stub.get_args('param').param, 'Subscribing to unknown stream with ID 42');
    });

});

test('peer event error handling', (override) => {
    override('compose_fade.update_faded_users', noop);

    let event = event_fixtures.subscription__peer_add;
    global.with_stub(function (stub) {
        override('stream_data.add_subscriber', noop);
        override('blueslip.warn', stub.f);
        dispatch(event);
        assert.deepEqual(stub.get_args('param').param, 'Cannot process peer_add event');
    });

    event = event_fixtures.subscription__peer_remove;
    global.with_stub(function (stub) {
        override('stream_data.remove_subscriber', noop);
        override('blueslip.warn', stub.f);
        dispatch(event);
        assert.deepEqual(stub.get_args('param').param, 'Cannot process peer_remove event.');
    });
});

