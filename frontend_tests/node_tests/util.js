set_global('$', global.make_zjquery());
set_global('blueslip', global.make_zblueslip({}));
set_global('document', {});

zrequire('util');

run_test('CachedValue', () => {
    var x = 5;

    var cv = new util.CachedValue({
        compute_value: function () {
            return x * 2;
        },
    });

    assert.equal(cv.get(), 10);

    x = 6;
    assert.equal(cv.get(), 10);
    cv.reset();
    assert.equal(cv.get(), 12);

});

run_test('get_reload_topic', () => {
    assert.equal(util.get_reload_topic({subject: 'foo'}), 'foo');
    assert.equal(util.get_reload_topic({topic: 'bar'}), 'bar');
});

run_test('extract_pm_recipients', () => {
    assert.equal(util.extract_pm_recipients('bob@foo.com, alice@foo.com').length, 2);
    assert.equal(util.extract_pm_recipients('bob@foo.com, ').length, 1);
});

run_test('is_pm_recipient', () => {
    var message = { reply_to: 'alice@example.com,bOb@exaMple.com,fred@example.com' };
    assert(util.is_pm_recipient('alice@example.com', message));
    assert(util.is_pm_recipient('bob@example.com', message));
    assert(!util.is_pm_recipient('unknown@example.com', message));
});

run_test('rtrim', () => {
    assert.equal(util.rtrim('foo'), 'foo');
    assert.equal(util.rtrim('  foo'), '  foo');
    assert.equal(util.rtrim('foo  '), 'foo');
});

run_test('lower_bound', () => {
    var arr = [10, 20, 30, 40, 50];
    assert.equal(util.lower_bound(arr, 5), 0);
    assert.equal(util.lower_bound(arr, 10), 0);
    assert.equal(util.lower_bound(arr, 15), 1);
    assert.equal(util.lower_bound(arr, 50), 4);
    assert.equal(util.lower_bound(arr, 55), 5);
    assert.equal(util.lower_bound(arr, 2, 4, 31), 3);

    arr = [{x: 10}, {x: 20}, {x: 30}];

    function compare(a, b) {
        return a.x < b;
    }

    assert.equal(util.lower_bound(arr, 5, compare), 0);
    assert.equal(util.lower_bound(arr, 10, compare), 0);
    assert.equal(util.lower_bound(arr, 15, compare), 1);

});

run_test('same_recipient', () => {
    assert(util.same_recipient(
        {type: 'stream', stream_id: 101, topic: 'Bar'},
        {type: 'stream', stream_id: 101, topic: 'bar'}));

    assert(!util.same_recipient(
        {type: 'stream', stream_id: 101, topic: 'Bar'},
        {type: 'stream', stream_id: 102, topic: 'whatever'}));

    assert(util.same_recipient(
        {type: 'private', to_user_ids: '101,102'},
        {type: 'private', to_user_ids: '101,102'}));

    assert(!util.same_recipient(
        {type: 'private', to_user_ids: '101,102'},
        {type: 'private', to_user_ids: '103'}));

    assert(!util.same_recipient(
        {type: 'stream', stream_id: 101, topic: 'Bar'},
        {type: 'private'}));

    assert(!util.same_recipient(
        {type: 'private', to_user_ids: undefined},
        {type: 'private'}));

    assert(!util.same_recipient(
        {type: 'unknown type'},
        {type: 'unknown type'}));

    assert(!util.same_recipient(
        undefined,
        {type: 'private'}));

    assert(!util.same_recipient(undefined, undefined));
});

run_test('robust_uri_decode', () => {
    assert.equal(util.robust_uri_decode('xxx%3Ayyy'), 'xxx:yyy');
    assert.equal(util.robust_uri_decode('xxx%3'), 'xxx');

    set_global('decodeURIComponent', function () { throw 'foo'; });
    try {
        util.robust_uri_decode('%E0%A4%A');
    } catch (e) {
        assert.equal(e, 'foo');
    }
});

run_test('get_message_topic', () => {
    blueslip.set_test_data('warn', 'programming error: message has no topic');
    assert.equal(util.get_message_topic({subject: 'foo'}), 'foo');
    blueslip.clear_test_data();
    assert.equal(util.get_message_topic({topic: 'bar'}), 'bar');
});

run_test('dumb_strcmp', () => {
    Intl.Collator = undefined;
    var strcmp = util.make_strcmp();
    assert.equal(strcmp('a', 'b'), -1);
    assert.equal(strcmp('c', 'c'), 0);
    assert.equal(strcmp('z', 'y'), 1);
});

run_test('get_edit_event_orig_topic', () => {
    assert.equal(util.get_edit_event_orig_topic({orig_subject: 'lunch'}), 'lunch');
});

run_test('is_mobile', () => {
    global.window.navigator = { userAgent: "Android" };
    assert(util.is_mobile());

    global.window.navigator = { userAgent: "Not mobile" };
    assert(!util.is_mobile());
});

run_test('array_compare', () => {
    assert(util.array_compare([], []));
    assert(util.array_compare([1, 2, 3], [1, 2, 3]));
    assert(!util.array_compare([1, 2], [1, 2, 3]));
    assert(!util.array_compare([1, 2, 3], [1, 2]));
    assert(!util.array_compare([1, 2, 3, 4], [1, 2, 3, 5]));
});

run_test('normalize_recipients', () => {
    assert.equal(
        util.normalize_recipients('ZOE@foo.com, bob@foo.com, alice@foo.com, AARON@foo.com '),
        'aaron@foo.com,alice@foo.com,bob@foo.com,zoe@foo.com');
});

run_test('random_int', () => {
    var min = 0;
    var max = 100;

    _.times(500, function () {
        var val = util.random_int(min, max);
        assert(min <= val);
        assert(val <= max);
        assert.equal(val, Math.floor(val));
    });
});

run_test('all_and_everyone_mentions_regexp', () => {
    var messages_with_all_mentions = [
        '@**all**',
        'some text before @**all** some text after',
        '@**all** some text after only',
        'some text before only @**all**',
    ];

    var messages_with_everyone_mentions = [
        '@**everyone**',
        'some text before @**everyone** some text after',
        '@**everyone** some text after only',
        'some text before only @**everyone**',
    ];

    var messages_with_stream_mentions = [
        '@**stream**',
        'some text before @**stream** some text after',
        '@**stream** some text after only',
        'some text before only @**stream**',
    ];

    var messages_without_all_mentions = [
        '@all',
        'some text before @all some text after',
        '`@everyone`',
        'some_email@everyone.com',
        '`@**everyone**`',
        'some_email@**everyone**.com',
    ];

    var messages_without_everyone_mentions = [
        'some text before @everyone some text after',
        '@everyone',
        '`@everyone`',
        'some_email@everyone.com',
        '`@**everyone**`',
        'some_email@**everyone**.com',
    ];

    var messages_without_stream_mentions = [
        'some text before @stream some text after',
        '@stream',
        '`@stream`',
        'some_email@stream.com',
        '`@**stream**`',
        'some_email@**stream**.com',
    ];

    var i;
    for (i = 0; i < messages_with_all_mentions.length; i += 1) {
        assert(util.is_all_or_everyone_mentioned(messages_with_all_mentions[i]));
    }

    for (i = 0; i < messages_with_everyone_mentions.length; i += 1) {
        assert(util.is_all_or_everyone_mentioned(messages_with_everyone_mentions[i]));
    }

    for (i = 0; i < messages_with_stream_mentions.length; i += 1) {
        assert(util.is_all_or_everyone_mentioned(messages_with_stream_mentions[i]));
    }

    for (i = 0; i < messages_without_all_mentions.length; i += 1) {
        assert(!util.is_all_or_everyone_mentioned(messages_without_everyone_mentions[i]));
    }

    for (i = 0; i < messages_without_everyone_mentions.length; i += 1) {
        assert(!util.is_all_or_everyone_mentioned(messages_without_everyone_mentions[i]));
    }

    for (i = 0; i < messages_without_stream_mentions.length; i += 1) {
        assert(!util.is_all_or_everyone_mentioned(messages_without_stream_mentions[i]));
    }
});

run_test('move_array_elements_to_front', () => {
    var strings = [
        'string1',
        'string3',
        'string2',
        'string4',
    ];
    var strings_selection = [
        'string4',
        'string1',
    ];
    var strings_expected = [
        'string1',
        'string4',
        'string3',
        'string2',
    ];
    var strings_no_selection = util.move_array_elements_to_front(strings, []);
    var strings_no_array = util.move_array_elements_to_front([], strings_selection);
    var strings_actual = util.move_array_elements_to_front(strings, strings_selection);
    var emails = [
        'test@zulip.com',
        'test@test.com',
        'test@localhost',
        'test@invalid@email',
        'something@zulip.com',
    ];
    var emails_selection = [
        'test@test.com',
        'test@localhost',
        'test@invalid@email',
    ];
    var emails_expected = [
        'test@test.com',
        'test@localhost',
        'test@invalid@email',
        'test@zulip.com',
        'something@zulip.com',
    ];
    var emails_actual = util.move_array_elements_to_front(emails, emails_selection);
    var i;
    assert(strings_no_selection.length === strings.length);
    for (i = 0; i < strings_no_selection.length; i += 1) {
        assert(strings_no_selection[i] === strings[i]);
    }
    assert(strings_no_array.length === 0);
    assert(strings_actual.length === strings_expected.length);
    for (i = 0; i < strings_actual.length; i += 1) {
        assert(strings_actual[i] === strings_expected[i]);
    }
    assert(emails_actual.length === emails_expected.length);
    for (i = 0; i < emails_actual.length; i += 1) {
        assert(emails_actual[i] === emails_expected[i]);
    }
});
