set_global('$', global.make_zjquery());
zrequire('util');
zrequire('compose_state');

/*
    For legacy reasons we mostly cover
    static/js/compose_state.js in
    frontend/node_tests/compose.js, but
    we should eventually migrate some of those
    tests to here.
*/

run_test('replying_to_message', () => {
    compose_state.stream_name('Social');
    compose_state.topic('lunch');

    assert(compose_state.replying_to_message({
        type: 'stream',
        stream: 'SoCIAl',
        topic: 'lunch',
    }));

    assert(!compose_state.replying_to_message({
        type: 'stream',
        stream: 'Social',
        topic: 'bogus',
    }));

    compose_state.recipient = () => 'hamlet@example.com';

    assert(compose_state.replying_to_message({
        type: 'private',
        reply_to: 'hamlet@example.com',
    }));

    assert(!compose_state.replying_to_message({
        type: 'private',
        reply_to: 'bogus@bogus.com',
    }));

    // Test defensive code.
    assert(!compose_state.replying_to_message({
        type: 'bogus',
    }));
});
