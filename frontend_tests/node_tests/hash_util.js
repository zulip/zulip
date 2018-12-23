zrequire('hash_util');
zrequire('stream_data');
zrequire('people');
zrequire('util');

var _window = {
    location: {
        protocol: "https:",
        host: "example.com",
        pathname: "/",
    },
};

global.patch_builtin('window', _window);

var hamlet = {
    user_id: 1,
    email: 'hamlet@example.com',
    full_name: 'Hamlet',
};

people.add_in_realm(hamlet);

var frontend = {
    stream_id: 99,
    name: 'frontend',
};

stream_data.add_sub('frontend', frontend);

run_test('hash_util', () => {
    // Test encodeHashComponent
    var str = 'https://www.zulipexample.com';
    var result1 = hash_util.encodeHashComponent(str);
    assert.equal(result1, 'https.3A.2F.2Fwww.2Ezulipexample.2Ecom');

    // Test decodeHashComponent
    var result2 = hash_util.decodeHashComponent(result1);
    assert.equal(result2, str);

    // Test encode_operand and decode_operand

    function encode_decode_operand(operator, operand, expected_val) {
        var encode_result = hash_util.encode_operand(operator, operand);
        assert.equal(encode_result, expected_val);
        var new_operand = encode_result;
        var decode_result = hash_util.decode_operand(operator, new_operand);
        assert.equal(decode_result, operand);
    }

    var operator = 'sender';
    var operand = hamlet.email;

    encode_decode_operand(operator, operand, '1-hamlet');

    operator = 'stream';
    operand = 'frontend';

    encode_decode_operand(operator, operand, '99-frontend');

    operator = 'topic';
    operand = 'testing 123';

    encode_decode_operand(operator, operand, 'testing.20123');
});

run_test('test_get_hash_category', () => {
    assert.deepEqual(
        hash_util.get_hash_category('streams/subscribed'),
        'streams'
    );
    assert.deepEqual(
        hash_util.get_hash_category('#settings/display-settings'),
        'settings'
    );
    assert.deepEqual(
        hash_util.get_hash_category('#drafts'),
        'drafts'
    );
    assert.deepEqual(
        hash_util.get_hash_category('invites'),
        'invites'
    );
});

run_test('test_get_hash_section', () => {
    assert.equal(
        hash_util.get_hash_section('streams/subscribed'),
        'subscribed'
    );
    assert.equal(
        hash_util.get_hash_section('#settings/your-account'),
        'your-account'
    );

    assert.equal(
        hash_util.get_hash_section('settings/10/general/'),
        '10'
    );

    assert.equal(
        hash_util.get_hash_section('#drafts'),
        ''
    );
    assert.equal(
        hash_util.get_hash_section(''),
        ''
    );
});

run_test('test_parse_narrow', () => {
    assert.deepEqual(
        hash_util.parse_narrow(['narrow', 'stream', '11-social']),
        [{negated: false, operator: 'stream', operand: '11-social'}]
    );

    assert.equal(
        hash_util.parse_narrow(['narrow', 'BOGUS']),
        undefined
    );
});

run_test('test_stream_edit_uri', () => {
    var sub = {
        name: 'research & development',
        stream_id: 42,
    };
    assert.equal(hash_util.stream_edit_uri(sub),
                 '#streams/42/research.20.26.20development');
});

run_test('test_by_conversation_and_time_uri', () => {
    var message = {
        type: 'stream',
        stream_id: frontend.stream_id,
        topic: 'testing',
        id: 42,
    };

    assert.equal(hash_util.by_conversation_and_time_uri(message),
                 'https://example.com/#narrow/stream/99-frontend/topic/testing/near/42');

    message = {
        type: 'private',
        display_recipient: [
            {
                user_id: hamlet.user_id,
            },
        ],
        id: 43,
    };

    assert.equal(hash_util.by_conversation_and_time_uri(message),
                 'https://example.com/#narrow/pm-with/1-pm/near/43');
});
