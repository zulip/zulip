zrequire('util');
zrequire('unread');
zrequire('stream_data');
zrequire('people');
zrequire('Handlebars', 'handlebars');
zrequire('Filter', 'js/filter');

set_global('message_store', {});
set_global('page_params', {});
set_global('feature_flags', {});

var me = {
    email: 'me@example.com',
    user_id: 30,
    full_name: 'Me Myself',
};

var joe = {
    email: 'joe@example.com',
    user_id: 31,
    full_name: 'joe',
};

var steve = {
    email: 'STEVE@foo.com',
    user_id: 32,
    full_name: 'steve',
};

people.add(me);
people.add(joe);
people.add(steve);
people.initialize_current_user(me.user_id);

function assert_same_operators(result, terms) {
    terms = _.map(terms, function (term) {
        // If negated flag is undefined, we explicitly
        // set it to false.
        var negated = term.negated;
        if (!negated) {
            negated = false;
        }
        return {
            negated: negated,
            operator: term.operator,
            operand: term.operand,
        };
    });
    assert.deepEqual(result, terms);
}

run_test('basics', () => {
    var operators = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'stream', operand: 'exclude_stream', negated: true},
        {operator: 'topic', operand: 'bar'},
    ];
    var filter = new Filter(operators);

    assert_same_operators(filter.operators(), operators);
    assert.deepEqual(filter.operands('stream'), ['foo']);

    assert(filter.has_operator('stream'));
    assert(!filter.has_operator('search'));

    assert(filter.has_operand('stream', 'foo'));
    assert(!filter.has_operand('stream', 'exclude_stream'));
    assert(!filter.has_operand('stream', 'nada'));

    assert(!filter.is_search());
    assert(filter.can_apply_locally());

    operators = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'topic', operand: 'bar'},
        {operator: 'search', operand: 'pizza'},
    ];
    filter = new Filter(operators);

    assert(filter.is_search());
    assert(!filter.can_apply_locally());
    assert(!filter.is_exactly('stream'));

    // If our only stream operator is negated, then for all intents and purposes,
    // we don't consider ourselves to have a stream operator, because we don't
    // want to have the stream in the tab bar or unsubscribe messaging, etc.
    operators = [
        {operator: 'stream', operand: 'exclude', negated: true},
    ];
    filter = new Filter(operators);
    assert(!filter.has_operator('stream'));

    // Negated searches are just like positive searches for our purposes, since
    // the search logic happens on the back end and we need to have can_apply_locally()
    // be false, and we want "Search results" in the tab bar.
    operators = [
        {operator: 'search', operand: 'stop_word', negated: true},
    ];
    filter = new Filter(operators);
    assert(filter.has_operator('search'));
    assert(!filter.can_apply_locally());

    // Similar logic applies to negated "has" searches.
    operators = [
        {operator: 'has', operand: 'images', negated: true},
    ];
    filter = new Filter(operators);
    assert(filter.has_operator('has'));
    assert(!filter.can_apply_locally());
});

run_test('topic_stuff', () => {
    var operators = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'topic', operand: 'old topic'},
    ];
    var filter = new Filter(operators);

    assert(filter.has_topic('foo', 'old topic'));
    assert(!filter.has_topic('wrong', 'old topic'));
    assert(!filter.has_topic('foo', 'wrong'));

    var new_filter = filter.filter_with_new_topic('new topic');

    assert.deepEqual(new_filter.operands('stream'), ['foo']);
    assert.deepEqual(new_filter.operands('topic'), ['new topic']);
});

run_test('new_style_operators', () => {
    var term = {
        operator: 'stream',
        operand: 'foo',
    };
    var operators = [term];
    var filter = new Filter(operators);

    assert.deepEqual(filter.operands('stream'), ['foo']);
    assert(filter.is_exactly('stream'));
});

run_test('public_operators', () => {
    var operators = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'in', operand: 'all'},
        {operator: 'topic', operand: 'bar'},
    ];

    var filter = new Filter(operators);
    assert_same_operators(filter.public_operators(), operators);
    assert(!filter.is_exactly('stream'));

    global.page_params.narrow_stream = 'default';
    operators = [
        {operator: 'stream', operand: 'default'},
    ];
    filter = new Filter(operators);
    assert_same_operators(filter.public_operators(), []);
});

run_test('canonicalizations', () => {
    assert.equal(Filter.canonicalize_operator('Is'), 'is');
    assert.equal(Filter.canonicalize_operator('Stream'), 'stream');
    assert.equal(Filter.canonicalize_operator('Subject'), 'topic');
    assert.equal(Filter.canonicalize_operator('FROM'), 'sender');

    var term;
    term = Filter.canonicalize_term({operator: 'Stream', operand: 'Denmark'});
    assert.equal(term.operator, 'stream');
    assert.equal(term.operand, 'Denmark');

    term = Filter.canonicalize_term({operator: 'sender', operand: 'me'});
    assert.equal(term.operator, 'sender');
    assert.equal(term.operand, 'me@example.com');

    term = Filter.canonicalize_term({operator: 'pm-with', operand: 'me'});
    assert.equal(term.operator, 'pm-with');
    assert.equal(term.operand, 'me@example.com');

    term = Filter.canonicalize_term({operator: 'search', operand: 'foo'});
    assert.equal(term.operator, 'search');
    assert.equal(term.operand, 'foo');

    term = Filter.canonicalize_term({operator: 'search', operand: 'fOO'});
    assert.equal(term.operator, 'search');
    assert.equal(term.operand, 'foo');

    term = Filter.canonicalize_term({operator: 'search', operand: 123});
    assert.equal(term.operator, 'search');
    assert.equal(term.operand, '123');

    term = Filter.canonicalize_term({operator: 'search', operand: 'abc “xyz”'});
    assert.equal(term.operator, 'search');
    assert.equal(term.operand, 'abc "xyz"');

    term = Filter.canonicalize_term({operator: 'has', operand: 'attachments'});
    assert.equal(term.operator, 'has');
    assert.equal(term.operand, 'attachment');

    term = Filter.canonicalize_term({operator: 'has', operand: 'images'});
    assert.equal(term.operator, 'has');
    assert.equal(term.operand, 'image');

    term = Filter.canonicalize_term({operator: 'has', operand: 'links'});
    assert.equal(term.operator, 'has');
    assert.equal(term.operand, 'link');

});

function get_predicate(operators) {
    operators = _.map(operators, function (op) {
        return {operator: op[0], operand: op[1]};
    });
    return new Filter(operators).predicate();
}

function make_sub(name, stream_id) {
    var sub = {
        name: name,
        stream_id: stream_id,
    };
    global.stream_data.add_sub(name, sub);
}

run_test('predicate_basics', () => {
    // Predicates are functions that accept a message object with the message
    // attributes (not content), and return true if the message belongs in a
    // given narrow. If the narrow parameters include a search, the predicate
    // passes through all messages.
    //
    // To keep these tests simple, we only pass objects with a few relevant attributes
    // rather than full-fledged message objects.

    var stream_id = 42;
    make_sub('Foo', stream_id);
    var predicate = get_predicate([['stream', 'Foo'], ['topic', 'Bar']]);

    assert(predicate({type: 'stream', stream_id: stream_id, topic: 'bar'}));
    assert(!predicate({type: 'stream', stream_id: stream_id, topic: 'whatever'}));
    assert(!predicate({type: 'stream', stream_id: 9999999}));
    assert(!predicate({type: 'private'}));

    // For old streams that we are no longer subscribed to, we may not have
    // a sub, but these should still match by stream name.
    predicate = get_predicate([['stream', 'old-Stream'], ['topic', 'Bar']]);
    assert(predicate({type: 'stream', stream: 'Old-stream', topic: 'bar'}));
    assert(!predicate({type: 'stream', stream: 'no-match', topic: 'whatever'}));

    predicate = get_predicate([['search', 'emoji']]);
    assert(predicate({}));

    predicate = get_predicate([['topic', 'Bar']]);
    assert(!predicate({type: 'private'}));

    predicate = get_predicate([['is', 'private']]);
    assert(predicate({type: 'private'}));
    assert(!predicate({type: 'stream'}));

    predicate = get_predicate([['is', 'starred']]);
    assert(predicate({starred: true}));
    assert(!predicate({starred: false}));

    predicate = get_predicate([['is', 'unread']]);
    assert(predicate({unread: true}));
    assert(!predicate({unread: false}));

    predicate = get_predicate([['is', 'alerted']]);
    assert(predicate({alerted: true}));
    assert(!predicate({alerted: false}));
    assert(!predicate({}));

    predicate = get_predicate([['is', 'mentioned']]);
    assert(predicate({mentioned: true}));
    assert(!predicate({mentioned: false}));

    predicate = get_predicate([['in', 'all']]);
    assert(predicate({}));

    var unknown_stream_id = 999;
    predicate = get_predicate([['in', 'home']]);
    assert(!predicate({stream_id: unknown_stream_id, stream: 'unknown'}));
    assert(predicate({type: 'private'}));
    global.page_params.narrow_stream = 'kiosk';
    assert(predicate({stream: 'kiosk'}));

    predicate = get_predicate([['near', 5]]);
    assert(predicate({}));

    predicate = get_predicate([['id', 5]]);
    assert(predicate({id: 5}));
    assert(!predicate({id: 6}));

    predicate = get_predicate([['id', 5], ['topic', 'lunch']]);
    assert(predicate({type: 'stream', id: 5, topic: 'lunch'}));
    assert(!predicate({type: 'stream', id: 5, topic: 'dinner'}));

    predicate = get_predicate([['sender', 'Joe@example.com']]);
    assert(predicate({sender_id: joe.user_id}));
    assert(!predicate({sender_email: steve.user_id}));

    predicate = get_predicate([['pm-with', 'Joe@example.com']]);
    assert(predicate({
        type: 'private',
        display_recipient: [{id: joe.user_id}],
    }));
    assert(!predicate({
        type: 'private',
        display_recipient: [{user_id: steve.user_id}],
    }));
    assert(!predicate({
        type: 'private',
        display_recipient: [{user_id: 999999}],
    }));
    assert(!predicate({type: 'stream'}));

    predicate = get_predicate([['pm-with', 'Joe@example.com,steve@foo.com']]);
    assert(predicate({
        type: 'private',
        display_recipient: [{user_id: joe.user_id}, {user_id: steve.user_id}],
    }));

    // Make sure your own email is ignored
    predicate = get_predicate([['pm-with', 'Joe@example.com,steve@foo.com,me@example.com']]);
    assert(predicate({
        type: 'private',
        display_recipient: [{user_id: joe.user_id}, {user_id: steve.user_id}],
    }));

    predicate = get_predicate([['pm-with', 'nobody@example.com']]);
    assert(!predicate({
        type: 'private',
        display_recipient: [{id: joe.user_id}],
    }));

    predicate = get_predicate([['group-pm-with', 'nobody@example.com']]);
    assert(!predicate({
        type: 'private',
        display_recipient: [{id: joe.user_id}],
    }));

    predicate = get_predicate([['group-pm-with', 'Joe@example.com']]);
    assert(predicate({
        type: 'private',
        display_recipient: [{id: joe.user_id}, {id: steve.user_id}, {id: me.user_id}],
    }));
    assert(!predicate({ // you must be a part of the group pm
        type: 'private',
        display_recipient: [{id: joe.user_id}, {id: steve.user_id}],
    }));
    assert(!predicate({
        type: 'private',
        display_recipient: [{id: steve.user_id}, {id: me.user_id}],
    }));
    assert(!predicate({type: 'stream'}));
});

run_test('negated_predicates', () => {
    var predicate;
    var narrow;

    var social_stream_id = 555;
    make_sub('social', social_stream_id);

    narrow = [
        {operator: 'stream', operand: 'social', negated: true},
    ];
    predicate = new Filter(narrow).predicate();
    assert(predicate({type: 'stream', stream_id: 999999}));
    assert(!predicate({type: 'stream', stream_id: social_stream_id}));
});

run_test('mit_exceptions', () => {
    global.page_params.realm_is_zephyr_mirror_realm = true;

    var predicate = get_predicate([['stream', 'Foo'], ['topic', 'personal']]);
    assert(predicate({type: 'stream', stream: 'foo', topic: 'personal'}));
    assert(predicate({type: 'stream', stream: 'foo.d', topic: 'personal'}));
    assert(predicate({type: 'stream', stream: 'foo.d', topic: ''}));
    assert(!predicate({type: 'stream', stream: 'wrong'}));
    assert(!predicate({type: 'stream', stream: 'foo', topic: 'whatever'}));
    assert(!predicate({type: 'private'}));

    predicate = get_predicate([['stream', 'Foo'], ['topic', 'bar']]);
    assert(predicate({type: 'stream', stream: 'foo', topic: 'bar.d'}));

    // Try to get the MIT regex to explode for an empty stream.
    var terms = [
        {operator: 'stream', operand: ''},
        {operator: 'topic', operand: 'bar'},
    ];
    predicate = new Filter(terms).predicate();
    assert(!predicate({type: 'stream', stream: 'foo', topic: 'bar'}));

    // Try to get the MIT regex to explode for an empty topic.
    terms = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'topic', operand: ''},
    ];
    predicate = new Filter(terms).predicate();
    assert(!predicate({type: 'stream', stream: 'foo', topic: 'bar'}));
});

run_test('predicate_edge_cases', () => {
    var predicate;
    // The code supports undefined as an operator to Filter, which results
    // in a predicate that accepts any message.
    predicate = new Filter().predicate();
    assert(predicate({}));

    // Upstream code should prevent Filter.predicate from being called with
    // invalid operator/operand combinations, but right now we just silently
    // return a function that accepts all messages.
    predicate = get_predicate([['in', 'bogus']]);
    assert(predicate({}));

    predicate = get_predicate([['bogus', 33]]);
    assert(predicate({}));

    predicate = get_predicate([['is', 'bogus']]);
    assert(predicate({}));

    // Exercise caching feature.
    var terms = [
        {operator: 'stream', operand: 'Foo'},
        {operator: 'topic', operand: 'bar'},
    ];
    var filter = new Filter(terms);
    filter.predicate();
    predicate = filter.predicate(); // get cached version
    assert(predicate({type: 'stream', stream: 'foo', topic: 'bar'}));

});

run_test('parse', () => {
    var string;
    var operators;

    function _test() {
        var result = Filter.parse(string);
        assert_same_operators(result, operators);
    }

    string = 'stream:Foo topic:Bar yo';
    operators = [
        {operator: 'stream', operand: 'Foo'},
        {operator: 'topic', operand: 'Bar'},
        {operator: 'search', operand: 'yo'},
    ];
    _test();

    string = 'pm-with:leo+test@zulip.com';
    operators = [
        {operator: 'pm-with', operand: 'leo+test@zulip.com'},
    ];
    _test();

    string = 'sender:leo+test@zulip.com';
    operators = [
        {operator: 'sender', operand: 'leo+test@zulip.com'},
    ];
    _test();

    string = 'stream:With+Space';
    operators = [
        {operator: 'stream', operand: 'With Space'},
    ];
    _test();

    string = 'stream:"with quoted space" topic:and separate';
    operators = [
        {operator: 'stream', operand: 'with quoted space'},
        {operator: 'topic', operand: 'and'},
        {operator: 'search', operand: 'separate'},
    ];
    _test();

    string = 'stream:"unclosed quote';
    operators = [
        {operator: 'stream', operand: 'unclosed quote'},
    ];
    _test();

    string = 'stream:""';
    operators = [
        {operator: 'stream', operand: ''},
    ];
    _test();

    string = 'https://www.google.com';
    operators = [
        {operator: 'search', operand: 'https://www.google.com'},
    ];
    _test();

    string = 'stream:foo -stream:exclude';
    operators = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'stream', operand: 'exclude', negated: true},
    ];
    _test();

    string = 'text stream:foo more text';
    operators = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'search', operand: 'text more text'},
    ];
    _test();

    string = 'stream:foo :emoji: are cool';
    operators = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'search', operand: ':emoji: are cool'},
    ];
    _test();

    string = ':stream: stream:foo :emoji: are cool';
    operators = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'search', operand: ':stream: :emoji: are cool'},
    ];
    _test();

    string = ':stream: stream:foo -:emoji: are cool';
    operators = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'search', operand: ':stream: -:emoji: are cool'},
    ];
    _test();

    string = '';
    operators = [];
    _test();

    string = 'stream: separated topic: "with space"';
    operators = [
        {operator: 'stream', operand: 'separated'},
        {operator: 'topic', operand: 'with space'},
    ];
    _test();
});

run_test('unparse', () => {
    var string;
    var operators;

    operators = [
        {operator: 'stream', operand: 'Foo'},
        {operator: 'topic', operand: 'Bar', negated: true},
        {operator: 'search', operand: 'yo'},
    ];
    string = 'stream:Foo -topic:Bar yo';
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [
        {operator: 'id', operand: 50},
    ];
    string = 'id:50';
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [
        {operator: 'near', operand: 150},
    ];
    string = 'near:150';
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [
        {operator: '', operand: ''},
    ];
    string = '';
    assert.deepEqual(Filter.unparse(operators), string);
});

run_test('describe', () => {
    var narrow;
    var string;

    narrow = [
        {operator: 'stream', operand: 'devel'},
        {operator: 'is', operand: 'starred'},
    ];
    string = 'stream devel, starred messages';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'stream', operand: 'river'},
        {operator: 'is', operand: 'unread'},
    ];
    string = 'stream river, unread messages';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'stream', operand: 'devel'},
        {operator: 'topic', operand: 'JS'},
    ];
    string = 'stream devel &gt; JS';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'is', operand: 'private'},
        {operator: 'search', operand: 'lunch'},
    ];
    string = 'private messages, search for lunch';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'id', operand: 99},
    ];
    string = 'message ID 99';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'in', operand: 'home'},
    ];
    string = 'messages in home';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'is', operand: 'mentioned'},
    ];
    string = '@-mentions';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'is', operand: 'alerted'},
    ];
    string = 'alerted messages';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'is', operand: 'something_we_do_not_support'},
    ];
    string = 'invalid something_we_do_not_support operand for is operator';
    assert.equal(Filter.describe(narrow), string);

    // this should be unreachable, but just in case
    narrow = [
        {operator: 'bogus', operand: 'foo'},
    ];
    string = 'unknown operator';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'stream', operand: 'devel'},
        {operator: 'topic', operand: 'JS', negated: true},
    ];
    string = 'stream devel, exclude topic JS';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'is', operand: 'private'},
        {operator: 'search', operand: 'lunch', negated: true},
    ];
    string = 'private messages, exclude lunch';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'stream', operand: 'devel'},
        {operator: 'is', operand: 'starred', negated: true},
    ];
    string = 'stream devel, exclude starred messages';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'stream', operand: 'devel'},
        {operator: 'has', operand: 'image', negated: true},
    ];
    string = 'stream devel, exclude messages with one or more image';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'has', operand: 'abc', negated: true},
        {operator: 'stream', operand: 'devel'},
    ];
    string = 'invalid abc operand for has operator, stream devel';
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: 'has', operand: 'image', negated: true},
        {operator: 'stream', operand: 'devel'},
    ];
    string = 'exclude messages with one or more image, stream devel';
    assert.equal(Filter.describe(narrow), string);

    narrow = [];
    string = 'all messages';
    assert.equal(Filter.describe(narrow), string);
});

run_test('is_functions', () => {
    var terms = [
        {operator: 'stream', operand: 'My Stream'},
    ];
    var filter = new Filter(terms);
    assert.equal(filter.is_exactly('stream'), true);
    assert.equal(filter.is_exactly('stream', 'topic'), false);
    assert.equal(filter.is_exactly('pm-with'), false);

    terms = [
        // try a non-orthodox ordering
        {operator: 'topic', operand: 'My Topic'},
        {operator: 'stream', operand: 'My Stream'},
    ];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by('stream'), true);
    assert.equal(filter.can_bucket_by('stream', 'topic'), true);
    assert.equal(filter.is_exactly('stream'), false);
    assert.equal(filter.is_exactly('stream', 'topic'), true);
    assert.equal(filter.is_exactly('pm-with'), false);
    assert.equal(filter.can_bucket_by('pm-with'), false);

    terms = [
        {operator: 'stream', operand: 'My Stream', negated: true},
        {operator: 'topic', operand: 'My Topic'},
    ];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by('stream'), false);
    assert.equal(filter.can_bucket_by('stream', 'topic'), false);
    assert.equal(filter.is_exactly('stream'), false);
    assert.equal(filter.is_exactly('stream', 'topic'), false);
    assert.equal(filter.is_exactly('pm-with'), false);

    terms = [
        {operator: 'pm-with', operand: 'foo@example.com', negated: true},
    ];
    filter = new Filter(terms);
    assert.equal(filter.is_exactly('stream'), false);
    assert.equal(filter.is_exactly('stream', 'topic'), false);
    assert.equal(filter.is_exactly('pm-with'), false);

    terms = [
        {operator: 'pm-with', operand: 'foo@example.com,bar@example.com'},
    ];
    filter = new Filter(terms);
    assert.equal(filter.is_exactly('stream'), false);
    assert.equal(filter.is_exactly('stream', 'topic'), false);
    assert.equal(filter.is_exactly('pm-with'), true);
    assert.equal(filter.is_exactly('is-mentioned'), false);
    assert.equal(filter.is_exactly('is-private'), false);

    terms = [
        {operator: 'is', operand: 'private'},
    ];
    filter = new Filter(terms);
    assert.equal(filter.is_exactly('is-mentioned'), false);
    assert.equal(filter.is_exactly('is-private'), true);

    terms = [
        {operator: 'is', operand: 'mentioned'},
    ];
    filter = new Filter(terms);
    assert.equal(filter.is_exactly('is-mentioned'), true);
    assert.equal(filter.is_exactly('is-private'), false);

    terms = [
        {operator: 'is', operand: 'mentioned'},
        {operator: 'is', operand: 'starred'},
    ];
    filter = new Filter(terms);
    assert.equal(filter.is_exactly('is-mentioned'), false);
    assert.equal(filter.is_exactly('is-private'), false);
    assert.equal(filter.can_bucket_by('is-mentioned'), true);
    assert.equal(filter.can_bucket_by('is-private'), false);

    // The call below returns false for somewhat arbitrary
    // reasons -- we say is-private has precedence over
    // is-starred.
    assert.equal(filter.can_bucket_by('is-starred'), false);

    terms = [
        {operator: 'is', operand: 'mentioned', negated: true},
    ];
    filter = new Filter(terms);
    assert.equal(filter.is_exactly('is-mentioned'), false);
    assert.equal(filter.is_exactly('is-private'), false);
});

run_test('term_type', () => {
    function assert_term_type(term, expected_term_type) {
        assert.equal(Filter.term_type(term), expected_term_type);
    }

    function term(operator, operand, negated) {
        return {
            operator: operator,
            operand: operand,
            negated: negated,
        };
    }

    assert_term_type(term('stream', 'whatever'), 'stream');
    assert_term_type(term('pm-with', 'whomever'), 'pm-with');
    assert_term_type(term('pm-with', 'whomever', true), 'not-pm-with');
    assert_term_type(term('is', 'private'), 'is-private');
    assert_term_type(term('has', 'link'), 'has-link');
    assert_term_type(term('has', 'attachment', true), 'not-has-attachment');

    function assert_term_sort(in_terms, expected) {
        const sorted_terms = Filter.sorted_term_types(in_terms);
        assert.deepEqual(sorted_terms, expected);
    }

    assert_term_sort(
        ['topic', 'stream', 'sender'],
        ['stream', 'topic', 'sender']
    );

    assert_term_sort(
        ['has-link', 'near', 'is-unread', 'pm-with'],
        ['pm-with', 'near', 'is-unread', 'has-link']
    );

    assert_term_sort(
        ['bogus', 'stream', 'topic'],
        ['stream', 'topic', 'bogus']
    );
    assert_term_sort(
        ['stream', 'topic', 'stream'],
        ['stream', 'stream', 'topic']
    );

    const terms = [
        {operator: 'topic', operand: 'lunch'},
        {operator: 'sender', operand: 'steve@foo.com'},
        {operator: 'stream', operand: 'Verona'},
    ];
    const filter = new Filter(terms);
    const term_types = filter.sorted_term_types();

    assert.deepEqual(term_types, ['stream', 'topic', 'sender']);
});

run_test('first_valid_id_from', () => {
    const terms = [
        {operator: 'is', operand: 'alerted'},
    ];

    const filter = new Filter(terms);

    const messages = {
        5: { id: 5, alerted: true },
        10: { id: 10 },
        20: { id: 20, alerted: true },
        30: { id: 30, type: 'stream' },
        40: { id: 40, alerted: false },
    };

    const msg_ids = [10, 20, 30, 40];

    message_store.get = () => {};

    assert.equal(filter.first_valid_id_from(msg_ids), undefined);

    message_store.get = (msg_id) => messages[msg_id];

    assert.equal(filter.first_valid_id_from(msg_ids), 20);
});

run_test('update_email', () => {
    var terms = [
        {operator: 'pm-with', operand: 'steve@foo.com'},
        {operator: 'sender', operand: 'steve@foo.com'},
        {operator: 'stream', operand: 'steve@foo.com'}, // try to be tricky
    ];
    var filter = new Filter(terms);
    filter.update_email(steve.user_id, 'showell@foo.com');
    assert.deepEqual(filter.operands('pm-with'), ['showell@foo.com']);
    assert.deepEqual(filter.operands('sender'), ['showell@foo.com']);
    assert.deepEqual(filter.operands('stream'), ['steve@foo.com']);
});


run_test('error_cases', () => {
    // This test just gives us 100% line coverage on defensive code that
    // should not be reached unless we break other code.
    people.pm_with_user_ids = function () {};

    var predicate = get_predicate([['pm-with', 'Joe@example.com']]);
    assert(!predicate({type: 'private'}));
});
